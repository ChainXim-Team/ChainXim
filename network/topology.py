import copy
import itertools
import json
import logging
import math
import os
import random
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import scipy.sparse as sp

import errors
import global_var
from functions import INT_LEN
from data import Message, Block

from .network_abc import (
    ERR_OUTAGE,
    GLOBAL,
    GetDataMsg,
    INVMsg,
    Network,
    Packet,
)

if TYPE_CHECKING:
    from miner.miner import Miner

logger = logging.getLogger(__name__)


_FREE = np.uint8(0)
_TRANSMITTING = np.uint8(1)
_EPSILON = 1e-12


class _TransferPool:
    """Reusable slots for transmissions that currently consume bandwidth."""

    def __init__(self, initial_capacity: int = 16):
        self._capacity = max(initial_capacity, 1)
        self.phase = np.full(self._capacity, _FREE, dtype=np.uint8)
        self.source_ids = np.empty(self._capacity, dtype=np.int32)
        self.target_ids = np.empty(self._capacity, dtype=np.int32)
        self.remaining_mb = np.empty(self._capacity, dtype=np.float64)
        self.total_size_mb = np.empty(self._capacity, dtype=np.float64)
        self.start_rounds = np.empty(self._capacity, dtype=np.int64)
        self.transfer_ids = np.empty(self._capacity, dtype=np.int64)
        self.packet_refs:list[TPPacket | None] = [None] * self._capacity

        self.active_slots = np.empty(self._capacity, dtype=np.int32)
        self.active_positions = np.full(self._capacity, -1, dtype=np.int32)
        self.active_count = 0
        self.free_slots = list(range(self._capacity - 1, -1, -1))
        self.edge_slots:dict[tuple[int, int], int] = {}
        self._next_transfer_id = 0

    def _grow(self):
        old_capacity = self._capacity
        self._capacity *= 2
        growth = self._capacity - old_capacity

        self.phase = np.concatenate((self.phase, np.full(growth, _FREE, dtype=np.uint8)))
        self.source_ids = np.resize(self.source_ids, self._capacity)
        self.target_ids = np.resize(self.target_ids, self._capacity)
        self.remaining_mb = np.resize(self.remaining_mb, self._capacity)
        self.total_size_mb = np.resize(self.total_size_mb, self._capacity)
        self.start_rounds = np.resize(self.start_rounds, self._capacity)
        self.transfer_ids = np.resize(self.transfer_ids, self._capacity)
        self.packet_refs.extend([None] * growth)

        self.active_slots = np.resize(self.active_slots, self._capacity)
        self.active_positions = np.concatenate((
            self.active_positions,
            np.full(growth, -1, dtype=np.int32),
        ))
        self.free_slots.extend(range(self._capacity - 1, old_capacity - 1, -1))

    def allocate(self, packet: "TPPacket", remaining_mb: float, round: int) -> int:
        edge = (packet.source, packet.target)
        if edge in self.edge_slots:
            raise RuntimeError(f"M{packet.source}->M{packet.target} already has a transmission")
        if remaining_mb <= 0:
            raise ValueError("Transmission size must be positive")
        if not self.free_slots:
            self._grow()

        slot = self.free_slots.pop()
        self.phase[slot] = _TRANSMITTING
        self.source_ids[slot] = packet.source
        self.target_ids[slot] = packet.target
        self.remaining_mb[slot] = remaining_mb
        self.total_size_mb[slot] = packet.payload.size
        self.start_rounds[slot] = round
        self.transfer_ids[slot] = self._next_transfer_id
        self._next_transfer_id += 1
        self.packet_refs[slot] = packet
        self.edge_slots[edge] = slot

        self.active_slots[self.active_count] = slot
        self.active_positions[slot] = self.active_count
        self.active_count += 1
        return slot

    def snapshot_active_slots(self) -> np.ndarray:
        return self.active_slots[:self.active_count].copy()

    def release(self, slot: int):
        if self.phase[slot] != _TRANSMITTING:
            raise RuntimeError(f"Slot {slot} is not transmitting")

        position = self.active_positions[slot]
        last_position = self.active_count - 1
        last_slot = self.active_slots[last_position]
        self.active_slots[position] = last_slot
        self.active_positions[last_slot] = position
        self.active_count -= 1
        self.active_positions[slot] = -1

        edge = (int(self.source_ids[slot]), int(self.target_ids[slot]))
        self.edge_slots.pop(edge, None)
        self.packet_refs[slot] = None
        self.phase[slot] = _FREE
        self.free_slots.append(slot)


class _BandwidthAllocator:
    @staticmethod
    def allocate_equal_share(
        active_slots: np.ndarray,
        source_ids: np.ndarray,
        target_ids: np.ndarray,
        remaining_mb: np.ndarray,
        upload_windows: np.ndarray,
        download_windows: np.ndarray,
        node_count: int,
    ) -> np.ndarray:
        if len(active_slots) == 0:
            return np.empty(0, dtype=np.float64)

        sources = source_ids[active_slots]
        targets = target_ids[active_slots]
        out_count = np.bincount(sources, minlength=node_count)
        in_count = np.bincount(targets, minlength=node_count)
        upload_share = upload_windows[sources] / out_count[sources]
        download_share = download_windows[targets] / in_count[targets]
        return np.minimum.reduce((
            remaining_mb[active_slots],
            upload_share,
            download_share,
        ))


@dataclass
class _PropagationEvent:
    packet: "TPPacket"
    source: int
    target: int
    transfer_id: int
    transmission_finish_round: int

class TPPacket(Packet):
    def __init__(self, payload: Message, round, source: int = None, target: int = None, 
                 type: str = GLOBAL, destination:int=None):
        """
        param
        ----
        payload (Message): 传输的消息
        round(int):进入网络的时间
        source (int: 转发的来源
        target (int): 本次转发的目标 
        type (str): 消息类型，GLOBAL代表转发给全网的消息，DIRECT代表仅转发给特定对象
        destination (int): 类型为DIRECT时的终点
        """
        super().__init__(source, payload)
        self.round = round
        self.target = target
        self.type = type
        self.destination = destination


class Link(object):
    '''拓扑网络中的数据包，包含路由相关信息'''
    def __init__(self, packet: TPPacket,  delay:int, outnetobj:"TopologyNetwork"):
        self.packet = packet
        self.delay = delay
        self.rcv_round = 0
        self.outnetobj = outnetobj  # 外部网络类实例


    def get_msg(self):
        return self.packet.payload
    
    def get_block_msg_name(self):
        if isinstance(self.packet.payload, Message):
            return self.packet.payload.name
        
    def target_id(self):
        return self.packet.target
    
    def target_miner(self):
        return self.outnetobj._miners[self.packet.target]
    
    def source_id(self):
        return self.packet.source

    def source_miner(self):
        return self.outnetobj._miners[self.packet.source]

    
class TopologyNetwork(Network):
    '''拓扑P2P网络'''                        
    def __init__(self, miners):
        super().__init__()
        self.withTopology = True
        self.withSegments = False

        self._miners:list[Miner] = miners
        for miner in self._miners:
            miner._join_network(self)

        # parameters, set by set_net_param()
        self._init_mode = None
        self._topology_path = None
        self._ave_degree = None
        self._bandwidth_honest = 0.5 # default 0.5 MB
        self._bandwidth_adv = 5 # default 5 MB
        self._upload_bandwidth_honest = None
        self._download_bandwidth_honest = None
        self._upload_bandwidth_adv = None
        self._download_bandwidth_adv = None
        self._propagation_delay = 0.0
        self._coo_edge_attribute = "bandwidth"
        self._node_bandwidth_path = None
        self._upload_windows = np.empty(self.MINER_NUM, dtype=np.float64)
        self._download_windows = np.empty(self.MINER_NUM, dtype=np.float64)
        self._outage_prob = 0
        self._show_label = False
        self._save_routing_graph = False
        self._save_routing_history = False
        self._directed = False

        # 拓扑图，初始默认全不连接
        self._graph = nx.Graph()
        self._graph.add_nodes_from(range(self.MINER_NUM))
        self._network_histroy = []
        self._node_pos = None #后面由set_node_pos生成

        # _active_links is retained for compatibility with old callers. New
        # transmissions are maintained by _transfer_pool.
        self._active_links:list[Link] = []
        self._transfer_pool = _TransferPool()
        self._propagation_events:dict[int, list[_PropagationEvent]] = defaultdict(list)

        self._dynamic = False
        self._tp_changes = []
        self._nextTpChangeRound=0
        self._avgTpChangeInterval=0
        self._edgeRemoveProb=0
        self._edgeAddProb=0
        self._maxPartitionsAllowed=0

        # status
        self._rcv_miners = defaultdict(set)
        self._routing_proc = defaultdict(list)
        self._stat_prop_times = {}
        self._block_num_bpt = []
        # 结果保存路径
        # NET_RESULT_PATH = global_var.get_net_result_path()
        # with open(NET_RESULT_PATH / 'routing_history.json', 'a+',  encoding='utf-8') as f:
        #     f.write('[')
        #     json.dump({"B0": {}}, f, indent=4)
        #     f.write(']')

    def __del__(self):
        # 在退出之前保存路由信息
        if getattr(self, "_save_routing_history", False):
            self.save_rest_routing_process()

    def set_net_param(self, init_mode = None, 
                      topology_path = None, 
                      ave_degree = None, 
                      bandwidth_honest = None, 
                      bandwidth_adv = None,
                      upload_bandwidth_honest = None,
                      download_bandwidth_honest = None,
                      upload_bandwidth_adv = None,
                      download_bandwidth_adv = None,
                      propagation_delay = None,
                      coo_edge_attribute = None,
                      node_bandwidth_path = None,
                      outage_prob = None, 
                      enable_resume_transfer = None,
                      directed = None,
                      dynamic = None, 
                      max_allowed_partitions = None,
                      avg_tp_change_interval = None, 
                      edge_remove_prob = None,
                      edge_add_prob = None,
                      stat_prop_times = None, 
                      show_label = None,
                      save_routing_graph = None,
                      save_routing_history = None,
                      rand_mode = None):
        ''' 
        set the network parameters

        param
        -----  
        gen_net_approach (str): 生成网络的方式, 'adj'邻接矩阵, 'coo'稀疏矩阵, 'rand'随机
        ave_degree (int):  If 'rand', set the average degree
        bandwidth_honest(float): bandwidth between honest miners and 
                                 between the honest and adversaries(MB/round)
        bandwidth_adv (float): bandwidth between adversaries(MB/round)
        directed (bool): Whether topology entries represent directed links.
        save_routing_graph (bool): Genarate routing graph at the end of simulation or not.
        show_label (bool): Show edge labels on network and routing graph or not. 
        '''
        if show_label is not None:
            self._show_label = show_label
        if bandwidth_honest is not None: # default 0.5 MB/round
            self._bandwidth_honest = bandwidth_honest 
        if bandwidth_adv is not None: # default 5 MB/round
            self._bandwidth_adv = bandwidth_adv 
        if upload_bandwidth_honest is not None:
            self._upload_bandwidth_honest = upload_bandwidth_honest
        if download_bandwidth_honest is not None:
            self._download_bandwidth_honest = download_bandwidth_honest
        if upload_bandwidth_adv is not None:
            self._upload_bandwidth_adv = upload_bandwidth_adv
        if download_bandwidth_adv is not None:
            self._download_bandwidth_adv = download_bandwidth_adv
        if propagation_delay is not None:
            self._propagation_delay = propagation_delay
        if coo_edge_attribute is not None:
            if coo_edge_attribute not in {"bandwidth", "latency"}:
                raise ValueError("coo_edge_attribute must be 'bandwidth' or 'latency'")
            self._coo_edge_attribute = coo_edge_attribute
        if node_bandwidth_path is not None:
            self._node_bandwidth_path = node_bandwidth_path
        self._initialize_bandwidth_windows()
        if topology_path is not None:
            self._topology_path = topology_path
        if directed is not None:
            self._directed = directed
        if init_mode is not None:
            if  init_mode == 'rand' and ave_degree is not None:
                self._init_mode = init_mode
                self._ave_degree = ave_degree
                self.network_generator(init_mode, ave_degree, rand_mode)
            else:
                self._init_mode = init_mode
                self.edge_prob = None
                self.network_generator(init_mode)
        if outage_prob is not None:
            self._outage_prob = outage_prob
        if enable_resume_transfer is not None:
            self._enableResumeTransfer = enable_resume_transfer
        if dynamic is not None:
            self._dynamic = dynamic
        if max_allowed_partitions is not None:
            self._maxPartitionsAllowed= max_allowed_partitions
            if max_allowed_partitions <= 1:
                self._maxPartitionsAllowed=1
        if avg_tp_change_interval is not None:
            self._avgTpChangeInterval = avg_tp_change_interval
            self._TpChangeSpan = 0.2*self._avgTpChangeInterval
            self._nextTpChangeRound += int(np.random.uniform(self._avgTpChangeInterval-self._TpChangeSpan,
                                                             self._avgTpChangeInterval+self._TpChangeSpan))
        if edge_remove_prob is not None:
            self._edgeRemoveProb = edge_remove_prob
        if edge_add_prob is not None:
            self._edgeAddProb = edge_add_prob
        if save_routing_graph is not None:
            self._save_routing_graph = save_routing_graph
        if save_routing_history is not None:
            self._save_routing_history = save_routing_history
        for rcv_rate in stat_prop_times:
            self._stat_prop_times.update({rcv_rate:0})
            self._block_num_bpt = [0 for _ in range(len(stat_prop_times))]
  

    def _initialize_bandwidth_windows(self):
        upload_honest = self._upload_bandwidth_honest or self._bandwidth_honest
        download_honest = self._download_bandwidth_honest or self._bandwidth_honest
        upload_adv = self._upload_bandwidth_adv or self._bandwidth_adv
        download_adv = self._download_bandwidth_adv or self._bandwidth_adv
        if min(upload_honest, download_honest, upload_adv, download_adv) <= 0:
            raise ValueError("All node upload and download bandwidths must be positive")
        self._upload_windows = np.array([
            upload_adv if miner._isAdversary else upload_honest
            for miner in self._miners
        ], dtype=np.float64)
        self._download_windows = np.array([
            download_adv if miner._isAdversary else download_honest
            for miner in self._miners
        ], dtype=np.float64)
        if self._node_bandwidth_path is not None:
            self._load_node_bandwidths(self._node_bandwidth_path)

    def _load_node_bandwidths(self, path: str):
        bandwidths = pd.read_csv(path)
        required_columns = {
            "node_id",
            "upload_MB_per_round",
            "download_MB_per_round",
        }
        missing_columns = required_columns - set(bandwidths.columns)
        if missing_columns:
            raise ValueError(f"Node bandwidth file is missing columns: {sorted(missing_columns)}")

        node_ids = bandwidths["node_id"].to_numpy(dtype=np.int64)
        if len(node_ids) != self.MINER_NUM or len(np.unique(node_ids)) != self.MINER_NUM:
            raise ValueError("Node bandwidth file must contain every node exactly once")
        if np.any(node_ids < 0) or np.any(node_ids >= self.MINER_NUM):
            raise ValueError("Node bandwidth file contains an out-of-range node_id")

        upload = bandwidths["upload_MB_per_round"].to_numpy(dtype=np.float64)
        download = bandwidths["download_MB_per_round"].to_numpy(dtype=np.float64)
        if not np.all(np.isfinite(upload)) or not np.all(np.isfinite(download)):
            raise ValueError("Node bandwidth values must be finite")
        if np.any(upload <= 0) or np.any(download <= 0):
            raise ValueError("Node bandwidth values must be positive")
        self._upload_windows[node_ids] = upload
        self._download_windows[node_ids] = download

    def access_network(self, new_msgs:list[Message|tuple[Message, float]], minerid:int, round:int, target:int,
                       sendTogether:bool = False):
        """Start one queued transmission for a directed neighbor channel.

        A tuple payload contains the remaining MB after an interrupted transfer.
        TopologyNetwork sends one message per channel at a time, so callers must
        not use ``sendTogether`` to create parallel transmissions on one edge.
        """
        if self.inv_handler(new_msgs):
            return None
        if len(new_msgs) != 1:
            raise ValueError("TopologyNetwork only accepts one transmission per channel")

        new_msg = new_msgs[0]
        remaining_mb = new_msg[1] if isinstance(new_msg, tuple) else None
        msg = new_msg[0] if isinstance(new_msg, tuple) else new_msg
        if not self.message_preprocessing(msg):
            return None
        if remaining_mb is None:
            remaining_mb = msg.size
        if remaining_mb <= 0:
            raise ValueError("TopologyNetwork cannot transmit an empty message")

        packet = TPPacket(msg, round, minerid, target)
        slot = self._transfer_pool.allocate(packet, remaining_mb, round)
        self._rcv_miners[self._message_name(packet)].add(minerid)
        logger.info("%s starts transmission: M%d -> M%d, round %d", msg.name, minerid, target, round)
        return slot
                
    def inv_handler(self, new_msgs:list[Message]):
        """先处理inv消息"""
        if not (len(new_msgs) >= 2 and isinstance(new_msgs[0], INVMsg) 
                and isinstance(new_msgs[1], GetDataMsg)):
            return False
        inv = new_msgs[0]
        getDataReply = new_msgs[1]
        getData = self._miners[inv.target]._NIC.reply_getdata(inv)
        for attr, value in getData.__dict__.items():
            setattr(getDataReply, attr, value)
        return True


    def cal_delay(self, msg: Message, source:int, target:int):
        """Legacy helper retained for callers using edge-bandwidth topologies."""
        bandwidth = self._graph.edges[source, target]['bandwidth']
        transmision_delay = math.ceil(msg.size / bandwidth)
        delay = self._miners[source]._NIC.processing_delay + transmision_delay
        return delay

    def _message_name(self, packet: TPPacket) -> str:
        payload = packet.payload
        if isinstance(payload, Message):
            return payload.name
        raise TypeError("TopologyNetwork only supports Message payloads")

    def _propagation_delay_for(self, source: int, target: int) -> float:
        return self._graph.edges[source, target].get("latency", getattr(self, "_propagation_delay", 0.0))

    def pre_diffuse(self, round) -> int:
        self.forward_process(round)
        has_work = self._transfer_pool.active_count > 0 or bool(self._propagation_events)
        return 1 if self._dynamic else int(has_work)

    def diffuse(self, round):
        """Advance transmitting and propagating messages by one round."""
        self.transfer_process(round)
        self.receive_process(round)
        if self._dynamic:
            self.topology_changing(round)
            
    def receive_process(self,round):
        """Deliver messages whose propagation phase ends this round."""
        events = self._propagation_events.pop(round, [])
        if not events:
            return
        propagated_messages = {}
        previous_rn = {}
        for event in events:
            rcv_state = self._miners[event.target]._NIC.nic_receive(event.packet)
            msg_name = self._message_name(event.packet)
            if not rcv_state[msg_name]:
                continue
            if msg_name not in previous_rn:
                previous_rn[msg_name] = len(self._rcv_miners[msg_name])
            if -1 not in self._rcv_miners[msg_name]:
                self._rcv_miners[msg_name].add(event.target)
                if self._save_routing_history:
                    self._routing_proc[msg_name].append(
                        [{event.source:event.packet.round}, {event.target:round}]
                    )
                propagated_messages[msg_name] = event.packet.payload

        for msg_name, msg in propagated_messages.items():
            self.stat_block_propagation_times(msg, round, previous_rn[msg_name])

    def transfer_process(self, round: int):
        """Allocate one round of node bandwidth to active transmissions."""
        self._drop_outaged_transfers(round)
        active_slots = self._transfer_pool.snapshot_active_slots()
        if len(active_slots) == 0:
            return

        transmitted = _BandwidthAllocator.allocate_equal_share(
            active_slots,
            self._transfer_pool.source_ids,
            self._transfer_pool.target_ids,
            self._transfer_pool.remaining_mb,
            self._upload_windows,
            self._download_windows,
            self.MINER_NUM,
        )
        self._transfer_pool.remaining_mb[active_slots] -= transmitted
        completed = active_slots[self._transfer_pool.remaining_mb[active_slots] <= _EPSILON]
        if len(completed) == 0:
            return
        completed = completed[np.argsort(self._transfer_pool.transfer_ids[completed])]
        for slot in completed:
            self._complete_transfer(int(slot), round)

    def _drop_outaged_transfers(self, round: int):
        if self._outage_prob <= 0:
            return
        for slot in self._transfer_pool.snapshot_active_slots():
            if random.uniform(0, 1) > self._outage_prob:
                continue
            self._cancel_transfer(int(slot), round, self._enableResumeTransfer)

    def _complete_transfer(self, slot: int, round: int):
        pool = self._transfer_pool
        packet = pool.packet_refs[slot]
        source = int(pool.source_ids[slot])
        target = int(pool.target_ids[slot])
        transfer_id = int(pool.transfer_ids[slot])
        pool.remaining_mb[slot] = 0.0
        self._miners[source]._NIC.on_transmission_complete(round, target, slot)
        pool.release(slot)

        latency = self._propagation_delay_for(source, target)
        if latency < 0 or not math.isfinite(latency):
            raise ValueError(f"Invalid propagation delay for M{source}->M{target}: {latency}")
        delivery_round = round + math.ceil(latency)
        self._propagation_events[delivery_round].append(_PropagationEvent(
            packet=packet,
            source=source,
            target=target,
            transfer_id=transfer_id,
            transmission_finish_round=round,
        ))

    def _cancel_transfer(self, slot: int, round: int, resume: bool):
        pool = self._transfer_pool
        packet = pool.packet_refs[slot]
        source = int(pool.source_ids[slot])
        target = int(pool.target_ids[slot])
        remaining_mb = float(pool.remaining_mb[slot]) if resume else None
        pool.release(slot)
        self._miners[source]._NIC.on_transmission_failed(
            round,
            target,
            packet.payload,
            remaining_mb,
        )
    
    def forward_process(self, round):
        """转发过程"""
        for m in self._miners:
            m._NIC.nic_forward(round)

    def topology_changing(self, round):
        if round != self._nextTpChangeRound:
            return
        changed = False
        change_op = {"round": round}
        for (node1, node2) in list(self._graph.edges):
            changed = changed or self.try_remove_edge(int(node1), int(node2), change_op)

        
        for node1 in list(self._graph.nodes):
            neighbors = set(self._graph[node1])
            non_neighbors = list(set(self._graph.nodes) - neighbors - {node1})
            if len(non_neighbors) == 0:
                continue
            node2 = random.choice(list(non_neighbors))
            changed = changed or self.try_add_edge(int(node1), int(node2), change_op,round)

        self._nextTpChangeRound += int(np.random.uniform(self._avgTpChangeInterval-self._TpChangeSpan,
                                                         self._avgTpChangeInterval+self._TpChangeSpan))

        if changed:
            sub_nets = [[int(n) for n in sn] for sn in self._connected_components()]
            # isolates = [[int(i)] for i in nx.isolates(self._graph)]
            isolates = []
            if len(sub_nets) + len(isolates) > 1:
                change_op.update({"partitions": sub_nets + isolates})
                logger.info("partitions: %s", str(sub_nets + isolates))
            self._tp_changes.append(change_op)
            self.write_tp_changes()
            # self.draw_and_save_network(f"round{round}")

    def write_tp_changes(self):
        if len(self._tp_changes)<=50:
            return
        NET_RESULT_PATH = global_var.get_net_result_path()
        with open(NET_RESULT_PATH / "tp_changes.yml", 'a') as file:
            # yaml.dump(self._tp_changes, file, sort_keys=False)
            for change in self._tp_changes:
                # 处理每个更改，手动构建YAML格式的字符串
                lines = ['- round: {}'.format(change.get('round', ''))]
                if 'adds' in change:
                    # 将添加的对格式化为一行
                    adds = ', '.join(['[{}, {}]'.format(*pair) for pair in change['adds']])
                    lines.append('  adds: [{}]'.format(adds))
                if 'removes' in change:
                    # 将移除的对格式化为一行
                    removes = ', '.join(['[{}, {}]'.format(*pair) for pair in change['removes']])
                    lines.append('  removes: [{}]'.format(removes))
                if 'partitions' in change:
                    # 对于每个分区，我们将其所有元素格式化为一行
                    pts_format = []
                    for pt in change['partitions']:
                        pt_format = ', '.join(str(node) for node in pt)
                        pts_format.append('[{}]'.format(pt_format))
                    partitions_str = ', '.join(pts_format)
                    lines.append('  partitions: [{}]'.format(partitions_str))
                file.write('\n'.join(lines) + '\n\n')
        self._tp_changes.clear()

    
    def try_remove_edge(self,node1:int, node2:int, change_op:dict):
        removed = False
        if self._miners[node1]._isAdversary and self._miners[node2]._isAdversary:
            return removed
        if random.uniform(0, 1) > self._edgeRemoveProb:
            return removed
        edge_attributes = self._graph.get_edge_data(node1, node2).copy()
        self._graph.remove_edge(node1, node2)
        sub_nets = self._number_connected_components()
        # isolates = nx.number_of_isolates(self._graph)
        isolates = 0
        # 若不允许产生分区但产生了分区，则重新连接
        if  sub_nets + isolates > self._maxPartitionsAllowed:
            self._graph.add_edge(node1, node2, **edge_attributes)
            return removed
        
        transfer_pool = getattr(self, "_transfer_pool", None)
        if transfer_pool is not None:
            cancelled_edges = [(node1, node2)]
            if not self._directed:
                cancelled_edges.append((node2, node1))
            for edge in cancelled_edges:
                slot = transfer_pool.edge_slots.get(edge)
                if slot is not None:
                    self._cancel_transfer(slot, change_op.get("round", 0), resume=False)
        self._miners[node1]._NIC.remove_neighbor(node2)
        if not self._directed:
            self._miners[node2]._NIC.remove_neighbor(node1)
        removed = True

        # 记录下拓扑变更操作
        if "removes" not in list(change_op.keys()):
            change_op["removes"]=[[node1, node2]]
        else:
            change_op["removes"].append([node1, node2])
            
        remove_links = []
        for i, link in enumerate(self._active_links):
            if (link.source_id(), link.target_id()) == (node1, node2):
                remove_links.append(i)
            elif (not self._directed and
                  (link.source_id(), link.target_id()) == (node2, node1)):
                remove_links.append(i)
        self._active_links = [link for i, link in enumerate(self._active_links) 
                            if i not in remove_links]
        return removed
        
                
    def try_add_edge(self,node1:int, node2:int, change_op:dict, round):
        added = False
        if self._miners[node1]._isAdversary and self._miners[node2]._isAdversary:
            return added
        if random.uniform(0, 1) > self._edgeAddProb:
            return added
        
        added = True
        self._graph.add_edge(node1, node2)
        # 设置带宽（MB/round）
        self._graph.edges[node1, node2]["bandwidth"] = self._bandwidth_honest
        self._graph.edges[node1, node2]["latency"] = getattr(self, "_propagation_delay", 0.0)
        self._miners[node1]._NIC.add_neighbor(node2, round)
        if not self._directed:
            self._miners[node2]._NIC.add_neighbor(node1, round)
        # 记录下拓扑变更操作
        if "adds" not in list(change_op.keys()):
            change_op["adds"]=[[node1, node2]]
        else:
            change_op["adds"].append([node1, node2])
        return added


    def stat_block_propagation_times(self, msg: Message, round, previous_rn):
        '''calculate the block propagation time'''
        if isinstance(msg, Block) is False:
            return
        rn = len(self._rcv_miners[msg.name])
        mn = self.MINER_NUM

        recv_ratio = rn / mn
        prev_ratio = previous_rn / mn

        rcv_rates = sorted(self._stat_prop_times.keys())

        # 区间判断逻辑
        for rcv_rate in rcv_rates:
            # 当前比例 > p，之前比例 =< p
            if recv_ratio >= rcv_rate >= prev_ratio:
                if -1 not in self._rcv_miners[msg.name]:
                    self._stat_prop_times[rcv_rate] += round-msg.blockhead.timestamp
                    self._block_num_bpt[rcv_rates.index(rcv_rate)] += 1
                    logger.debug(f"{msg.name}:{rn},{rcv_rate} at round {round}")
        
        if rn == mn and -1 not in self._rcv_miners[msg.name]:
            self._rcv_miners[msg.name] = {-1}
            self.save_specific_routing_process(msg.name)
    
    def save_specific_routing_process(self, block_name:str):
        if self._save_routing_history:
            with open(self.NET_RESULT_PATH / 'routing_history.json', 'a+', 
                    encoding = 'utf-8') as f:
                json.dump({block_name: self._routing_proc[block_name]},f)
                self._routing_proc.pop(block_name)
                f.write('\n')
    
    def save_rest_routing_process(self):
        with open(self.NET_RESULT_PATH / 'routing_history.json', 'a+', 
                  encoding = 'utf-8') as f:
            for block_name, routing in self._routing_proc.items():
                json.dump({block_name: routing},f)
                f.write('\n')
            self._routing_proc.clear()

    def cal_block_propagation_times(self):
        rcv_rates = [k for k in self._stat_prop_times.keys()]
        for i ,  rcv_rate in enumerate(rcv_rates):
            total_bpt = self._stat_prop_times[rcv_rate ]
            total_num = self._block_num_bpt[i]
            if total_num == 0:
                continue
            self._stat_prop_times[rcv_rate] = round(total_bpt/total_num, 3)
        
        return self._stat_prop_times
    

    def is_small_network(self):
        return self._graph.number_of_nodes() <= 2000 and self._graph.number_of_edges() <= 10000

    def _new_graph(self):
        return nx.DiGraph() if self._directed else nx.Graph()

    def _connected_components(self):
        if self._directed:
            return nx.strongly_connected_components(self._graph)
        return nx.connected_components(self._graph)

    def _number_connected_components(self):
        if self._directed:
            return nx.number_strongly_connected_components(self._graph)
        return nx.number_connected_components(self._graph)

    def _is_connected(self):
        if self._graph.number_of_nodes() == 0:
            return False
        if self._directed:
            return nx.is_strongly_connected(self._graph)
        return nx.is_connected(self._graph)

    def network_generator(self, gen_net_approach, ave_degree=None, rand_mode=None):
        '''
        根据csv文件的邻接矩'adj'或coo稀疏矩阵'coo'生成网络拓扑    
        '''
        # read from csv finished
        try:
            if gen_net_approach == 'adj':
                self.gen_network_by_adj()
            elif gen_net_approach == 'coo':
                self.gen_network_by_coo()
            elif gen_net_approach == 'rand' and ave_degree is not None:
                self.gen_network_rand(ave_degree, rand_mode)
            else:
                raise errors.NetGenError('网络生成方式错误！')
            
            #检查是否有孤立节点或不连通部分
            if nx.number_of_isolates(self._graph) != 0:
                raise errors.NetUnconnetedError(f'Isolated nodes in the network! '
                    f'{list(nx.isolates(self._graph))}')
            if not self._is_connected():
                if gen_net_approach != 'rand':
                    raise errors.NetIsoError('Brain-split in the newtork! ')
                retry_num = 10
                for _ in range(retry_num):
                    self.gen_network_rand(ave_degree, rand_mode)
                    if self._is_connected():
                        break
                if not self._is_connected():
                    raise errors.NetIsoError(f'Brain-split in the newtork! '
                        f'Choose an appropriate degree, current: {ave_degree}')
                
            
            # 邻居节点保存到各miner的neighbor_list中
            for minerid in list(self._graph.nodes):
                self._miners[int(minerid)]._NIC._neighbors = \
                    list(self._graph.neighbors(int(minerid)))
            for miner in self._miners:
                miner._NIC.init_queues()
                
            # 结果展示和保存，过大的网络避免画图和保存结果
            if self.is_small_network():
                self.draw_and_save_network()
            self.save_network_attribute()
                
        except (errors.NetMinerNumError, errors.NetAdjError, errors.NetIsoError, 
                errors.NetUnconnetedError, errors.NetGenError) as error:
            print(error)
            sys.exit(0)
    
    def get_neighbor_len(self, G: nx.Graph, minerid):
        return len(list(G.neighbors(minerid)))

    def random_graph_with_fixed_degree(self, n, ave_degree):
        G = nx.Graph()
        G.add_nodes_from(range(n))
        edge_adding_queue = list(range(n))
        random.shuffle(edge_adding_queue)
        ready_nodes = []
        while edge_adding_queue:
            i = edge_adding_queue.pop()
            neighbor_len = self.get_neighbor_len(G, i)
            if neighbor_len >= ave_degree:
                continue
            if len(edge_adding_queue) >= ave_degree - neighbor_len:
                neighbor_lens = map(self.get_neighbor_len, [G]*len(edge_adding_queue), edge_adding_queue)
                remaining_edges = np.clip(ave_degree - np.fromiter(neighbor_lens, np.float16), 0.0001, None)
                new_neighbor = np.random.choice(edge_adding_queue,
                                                int(ave_degree) - neighbor_len,
                                                replace=False,
                                                p=remaining_edges/remaining_edges.sum())
            else:
                new_neighbor = edge_adding_queue + random.sample(ready_nodes,
                                                                 int(ave_degree) - neighbor_len - len(edge_adding_queue))
            for j in new_neighbor:
                G.add_edge(i, j)
            ready_nodes.append(i)
        return G

    def gen_network_rand(self, ave_degree, rand_mode):
        """生成随机图"""
        if rand_mode == 'homogeneous':
            graph = self.random_graph_with_fixed_degree(self.MINER_NUM, ave_degree)
        elif rand_mode == 'binomial':
            graph = nx.binomial_graph(self.MINER_NUM,
                                      ave_degree/(self.MINER_NUM-1))
        else:
            raise errors.NetGenError(f'Random network mode {rand_mode} is not supported!')
        # 防止出现孤立节点
        if nx.number_of_isolates(graph) > 0:
            iso_nodes = list(nx.isolates(graph))
            not_iso_nodes = [nd for nd in list(graph.nodes) if nd not in iso_nodes]
            targets = np.random.choice(not_iso_nodes, len(iso_nodes))
            for m1, m2 in zip(iso_nodes, targets):
                graph.add_edge(m1, m2)
        if self._directed:
            self._graph = nx.DiGraph()
            self._graph.add_nodes_from(graph.nodes)
            self._graph.add_edges_from(
                (source, target)
                for node1, node2 in graph.edges
                for source, target in ((node1, node2), (node2, node1))
            )
        else:
            self._graph = graph
        # 将攻击者集团的各个矿工相连
        for m1,m2 in itertools.combinations(range(self.MINER_NUM), 2):
            if self._miners[m1]._isAdversary and self._miners[m2]._isAdversary:
                if not self._graph.has_edge(m1, m2):
                    self._graph.add_edge(m1, m2)
                if self._directed and not self._graph.has_edge(m2, m1):
                    self._graph.add_edge(m2, m1)
        # 设置带宽（MB/round）
        bw_honest = self._bandwidth_honest
        bw_adv = self._bandwidth_adv
        bandwidths = {(u,v):(bw_adv if self._miners[u]._isAdversary
                      and self._miners[v]._isAdversary else bw_honest)
                      for u,v in self._graph.edges}
        nx.set_edge_attributes(self._graph, bandwidths, "bandwidth")
        nx.set_edge_attributes(self._graph, getattr(self, "_propagation_delay", 0.0), "latency")


    def gen_network_by_adj(self):
        """
        如果读取邻接矩阵,则固定节点间的带宽0.5MB/round
        bandwidth单位:bit/round
        """
        # 读取csv文件的邻接矩阵
        self.read_adj_from_csv()
        self._graph = self._new_graph()
        # 生成节点
        self._graph.add_nodes_from([i for i in range(self.MINER_NUM)])
        # 生成边
        for m1 in range(len(self.tp_adjacency_matrix)):
            start = 0 if self._directed else m1
            for m2 in range(start, len(self.tp_adjacency_matrix)):
                if self.tp_adjacency_matrix[m1, m2] == 1:
                    self._graph.add_edge(m1, m2)
        # 设置带宽（MB/round）
        bw_honest = self._bandwidth_honest
        bw_adv = self._bandwidth_adv
        bandwidths = {(u,v):(bw_adv if self._miners[u]._isAdversary
                      and self._miners[v]._isAdversary else bw_honest)
                      for u,v in self._graph.edges}
        nx.set_edge_attributes(self._graph, bandwidths, "bandwidth")
        nx.set_edge_attributes(self._graph, getattr(self, "_propagation_delay", 0.0), "latency")
                    


    def gen_network_by_coo(self):
        """如果读取'coo'稀疏矩阵,则带宽由用户规定"""
        # 第一行是行(from)
        # 第二行是列(to)(在无向图中无所谓from to)
        # 第三行是bandwidth:bit/round
        csv_file = self._topology_path or 'conf/topologies/circular16_coo.csv'
        tp_coo_dataframe = pd.read_csv(csv_file, header=None, index_col=None)
        tp_coo_ndarray = tp_coo_dataframe.values
        row = np.array([int(i) for i in tp_coo_ndarray[0]])
        col = np.array([int(i) for i in tp_coo_ndarray[1]])
        edge_values = np.array([float(i) for i in tp_coo_ndarray[2]])
        if not (len(row) == len(col) == len(edge_values)):
            raise errors.NetAdjError('COO拓扑的from、to和attribute数量不一致!')
        if np.any(row < 0) or np.any(row >= self.MINER_NUM):
            raise errors.NetAdjError('COO拓扑包含越界的from节点!')
        if np.any(col < 0) or np.any(col >= self.MINER_NUM):
            raise errors.NetAdjError('COO拓扑包含越界的to节点!')
        if not np.all(np.isfinite(edge_values)):
            raise errors.NetAdjError('COO拓扑属性必须是有限数!')
        edge_attribute = getattr(self, "_coo_edge_attribute", "bandwidth")
        if edge_attribute == "bandwidth" and np.any(edge_values <= 0):
            raise errors.NetAdjError('COO拓扑的bandwidth必须大于0!')
        if edge_attribute == "latency" and np.any(edge_values < 0):
            raise errors.NetAdjError('COO拓扑的latency不能小于0!')
        if self._directed:
            adjacency_row = row
            adjacency_col = col
        else:
            adjacency_row = np.hstack([row, col])
            adjacency_col = np.hstack([col, row])
        adj_values = np.ones(len(adjacency_row))
        self.tp_adjacency_matrix = sp.coo_matrix(
            (adj_values, (adjacency_row, adjacency_col)),
            shape=(self.MINER_NUM, self.MINER_NUM))
        self._graph = self._new_graph()
        self._graph.add_nodes_from([i for i in range(self.MINER_NUM)])
        for edge_idx, (src, tgt) in enumerate(zip(row, col)):
            attributes = {
                "bandwidth": self._bandwidth_honest,
                "latency": getattr(self, "_propagation_delay", 0.0),
            }
            if edge_attribute == "latency":
                attributes["latency"] = edge_values[edge_idx]
            else:
                attributes["bandwidth"] = edge_values[edge_idx]
            self._graph.add_edge(src, tgt, **attributes)


    def read_adj_from_csv(self):
        """读取邻接矩阵adj"""
        # 读取csv文件并转化为ndarray类型,行是from 列是to
        csv_file = self._topology_path or 'conf/topologies/default_adj.csv'
        topology_ndarray  = pd.read_csv(csv_file, header=None, index_col=None).values
        # 判断邻接矩阵是否规范
        if np.isnan(topology_ndarray).any():
            raise errors.NetAdjError('邻接矩阵不规范!(存在缺失)')
        if topology_ndarray.shape[0] != topology_ndarray.shape[1]:  # 不是方阵
            raise errors.NetAdjError('邻接矩阵不规范!(row!=column)')
        if len(topology_ndarray) != self.MINER_NUM:  # 行数与环境定义的矿工数量不同
            raise errors.NetMinerNumError('矿工数量与环境定义不符!')
        if not self._directed and not np.array_equal(topology_ndarray, topology_ndarray.T):
            raise errors.NetAdjError('无向图邻接矩阵不规范!(不是对称阵)')
        if not np.all(np.diag(topology_ndarray) == 0):
            raise errors.NetAdjError('邻接矩阵不规范!(对角元素不为0)')
        self.tp_adjacency_matrix = (topology_ndarray != 0).astype(int)

    def read_adj_from_csv_undirected(self):
        """兼容原有的无向邻接矩阵读取接口"""
        self.read_adj_from_csv()

    def save_network_attribute(self):
        '''保存网络参数'''
        network_attributes={
            'miner_num':self.MINER_NUM,
            'Generate Approach':self._init_mode,
            'Generate Edge Probability':self._ave_degree/self.MINER_NUM if self._init_mode == 'rand' else None,
            'Degree Histogram': nx.degree_histogram(self._graph),
            "Average Degree": sum(dict(nx.degree(self._graph)).values())/len(self._graph.nodes),
            'Average Cluster Coefficient':round(nx.average_clustering(self._graph), 3),
            'Degree Assortativity':round(nx.degree_assortativity_coefficient(self._graph), 3),
        }
        if self.is_small_network():
            network_attributes['Diameter'] = nx.diameter(self._graph)
            network_attributes['Average Shortest Path Length'] = round(nx.average_shortest_path_length(self._graph), 3)
        else: 
            from networkx.algorithms.approximation import diameter
            def approximate_avg_shortest_path(G, samples=1000):
                nodes = list(G.nodes())
                sampled_nodes = random.sample(nodes, samples)
                total_dist = 0
                for node in sampled_nodes:
                    lengths = nx.single_source_shortest_path_length(G, node)
                    total_dist += sum(lengths.values())
                return total_dist / (len(sampled_nodes) * (len(G) - 1))

            network_attributes['Diameter'] = diameter(self._graph)
            network_attributes['Average Shortest Path Length'] = round(approximate_avg_shortest_path(self._graph), 3)

        NET_RESULT_PATH = global_var.get_net_result_path()
        with open(NET_RESULT_PATH / 'Network Attributes.txt', 'a+', encoding='utf-8') as f:
            f.write('Network Attributes'+'\n')
            print('Network Attributes')
            for k,v in network_attributes.items():
                f.write(str(k)+': '+str(v)+'\n')
                print(' '*4 + str(k)+': '+str(v))
            print('\n')

    
    def get_node_pos(self):
        '''使用spring_layout设置节点位置'''
        if self._node_pos is None:
            self._node_pos = nx.spring_layout(self._graph, seed=50)
        return self._node_pos
        

    def draw_and_save_network(self, file_name = None):
        """
        展示和保存网络拓扑图self.network_graph
        """
        node_pos = self.get_node_pos()
        # plt.ion()
        # plt.figure(figsize=(12,10))
        node_size = 200*3/self.MINER_NUM**0.5
        font_size = 30/self.MINER_NUM**0.5
        line_width = 3/self.MINER_NUM**0.5
        #nx.draw(self.network_graph, self.draw_pos, with_labels=True,
        #  node_size=node_size,font_size=30/(self.MINER_NUM)^0.5,width=3/self.MINER_NUM)
        node_colors = ["red" if self._miners[n]._isAdversary else '#1f78b4'  
                            for n,d in self._graph.nodes(data=True)]
        nx.draw_networkx_nodes(self._graph, pos = node_pos, 
                                node_color = node_colors, node_size=node_size)
        nx.draw_networkx_labels(self._graph, pos = node_pos, 
                                font_size = font_size, font_family = 'times new roman')
        edge_labels = {}
        for src, tgt in self._graph.edges:
            bandwidth = self._graph.get_edge_data(src, tgt)['bandwidth']
            edge_labels[(src, tgt)] = f'BW:{bandwidth}'
        nx.draw_networkx_edges(self._graph, pos=node_pos, 
                               width = line_width, node_size=node_size)
        if self._show_label:
            nx.draw_networkx_edge_labels(self._graph, node_pos,
                                         edge_labels = edge_labels,
                                         font_size = 12/self.MINER_NUM**0.5, 
                                         font_family ='times new roman')
        file_name = "network topology" if file_name is None else file_name

        RESULT_PATH = global_var.get_net_result_path()
        plt.box(False)
        plt.margins(0)
        plt.savefig(RESULT_PATH / f'{file_name}.svg', bbox_inches="tight")
        #plt.pause(1)
        plt.close()
        #plt.ioff()



    def write_routing_to_json(self, block_packet:Link):
        """
        每当一个block传播结束,将其路由结果记录在json文件中
        json文件包含origin_miner和routing_histroy两种信息
        """
        if not isinstance(block_packet.packet, Message):
            return

        bp = block_packet
        with open(self.NET_RESULT_PATH / 'routing_history.json', 'a+', encoding = 'utf-8') as f:
            f.seek(f.tell() - 1, os.SEEK_SET)
            f.truncate()
            f.write(',')
            bp.routing_histroy = {str(k): bp.routing_histroy[k] for k in bp.routing_histroy}
            json.dump({str(bp.packet.name): {'origin_miner': bp.minerid, 'routing_histroy': bp.routing_histroy}},
                      f, indent=2)
            f.write(']')


    def gen_routing_gragh_from_json(self):
        """
        读取Result->Network Routing文件夹下的routing_histroy.json,并将其转化为routing_gragh
        """
        if self._save_routing_graph is False:
            print('Fail to generate routing gragh for each block from json.')
        elif self._save_routing_graph is True:  
            print('Generate routing gragh for each block from json...')
            NET_RESULT_PATH = global_var.get_net_result_path()
            with open(NET_RESULT_PATH / 'routing_history.json', 'r', encoding = 'utf-8') as load_obj:
                a = json.load(load_obj)
                for v_dict in a:
                    for blockname, origin_routing_dict in v_dict.items():
                        if blockname != 'B0':
                            for k, v in origin_routing_dict.items():
                                if k == 'origin_miner':
                                    origin_miner = v
                                if k == 'routing_histroy':
                                    rh = v
                                    rh = {tuple(eval(ki)): rh[ki] for ki, _ in rh.items()}
                            self.gen_routing_gragh(blockname, rh, origin_miner)
                            print(f'\rgenerate routing gragh of {blockname} successfully', end="", flush=True)
            print('Routing gragh finished')
            

    def gen_routing_gragh(self, blockname, routing_histroy_single_block, origin_miner):
        """
        对单个区块生成路由图routing_gragh
        """
        # 生成有向图
        route_graph = nx.DiGraph()

        route_graph.add_nodes_from(self._graph.nodes)

        for (source_node, target_node), strounds in routing_histroy_single_block.items():
            route_graph.add_edge(source_node, target_node, trans_histroy=strounds)

        # 画图和保存结果
        # 处理节点颜色
        node_colors = []
        for n, d in route_graph.nodes(data=True):
            if self._miners[n]._isAdversary and n != origin_miner:
                node_colors.append("red")
            elif n == origin_miner:
                node_colors.append("green")
            else:
                node_colors.append('#1f78b4')
        node_size = 100*3/self.MINER_NUM**0.5
        nx.draw_networkx_nodes(
            route_graph, 
            pos = self._node_pos, 
            node_size = node_size,
            node_color = node_colors)
        nx.draw_networkx_labels(
            route_graph, 
            pos = self._node_pos, 
            font_size = 30/self.MINER_NUM**0.5,
            font_family = 'times new roman')
        # 对边进行分类，分为单向未传播完成的、双向未传播完成的、已传播完成的
        edges_not_complete_single = [
            (u, v) for u, v, d in route_graph.edges(data=True) 
            if d["trans_histroy"][1] == 0 and (v, u) not in  route_graph.edges()]
        edges_not_complete_double = [
            (u, v) for u, v, d in route_graph.edges(data=True) 
            if d["trans_histroy"][1] == 0 and (v, u) in  route_graph.edges() 
            and u > v]
        edges_complete = [
            ed for ed in [(u, v) for u, v, d in route_graph.edges(data=True) 
            if (u, v)not in edges_not_complete_single 
            and (u, v) not in edges_not_complete_double 
            and (v, u) not in edges_not_complete_double]]
        # 画边
        width = 3/self.MINER_NUM**0.5
        nx.draw_networkx_edges(
            route_graph, 
            self._node_pos, 
            edgelist = edges_complete, 
            edge_color = 'black', 
            width = width,
            alpha = 1,
            node_size = node_size,
            arrowsize = 30/self.MINER_NUM**0.5)
        nx.draw_networkx_edges(
            route_graph, 
            self._node_pos, 
            edgelist = edges_not_complete_single, 
            edge_color = 'black',
            width = width,style='--', 
            alpha = 0.3,
            node_size = node_size,
            arrowsize = 30/self.MINER_NUM**0.5)
        nx.draw_networkx_edges(
            route_graph, 
            self._node_pos, 
            edgelist = edges_not_complete_double, 
            edge_color = 'black',
            width = width,style='--', 
            alpha = 0.3,
            node_size = node_size,
            arrowstyle = '<|-|>',
            arrowsize = 30/self.MINER_NUM**0.5)                      
        # 没有传播到的边用虚线画
        edges_list_extra = []
        for (u, v) in self._graph.edges:
            if (u, v) in route_graph.edges:
                continue
            if not self._directed and (v, u) in route_graph.edges:
                continue
            route_graph.add_edge(u, v, trans_histroy=None)
            edges_list_extra.append((u, v))
        nx.draw_networkx_edges(
            route_graph, 
            pos = self._node_pos, 
            edgelist = edges_list_extra, 
            edge_color = 'black',
            width = 3/self.MINER_NUM**0.5,
            alpha = 0.3, 
            style = '--', 
            arrows = self._directed)
        # 处理边上的label，对单向的双向和分别处理
        if self._show_label:
            # 单向
            edge_labels = {
                (u, v): f'{u}-{v}:{d["trans_histroy"]}' 
                        for u, v, d in route_graph.edges(data=True)
                        if (v, u) not in route_graph.edges()}
            # 双向
            edge_labels.update(dict(
                [((u, v), f'{u}-{v}:{d["trans_histroy"]}\n\n'
                          f'{v}-{u}:{route_graph.edges[(v, u)]["trans_histroy"]}')
                          for u, v, d in route_graph.edges(data=True) 
                          if v > u and (v, u) in route_graph.edges()]))
            nx.draw_networkx_edge_labels(
                route_graph, 
                self._node_pos, 
                edge_labels = edge_labels, 
                font_size = 7*2/self.MINER_NUM**0.5,
                font_family = 'times new roman')
        #保存svg图片
        NET_RESULT_PATH = global_var.get_net_result_path()
        plt.savefig(NET_RESULT_PATH / (f'routing_graph{blockname}.svg'))
        plt.close()
