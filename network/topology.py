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
        self._outage_prob = 0
        self._show_label = False
        self._save_routing_graph = False
        self._save_routing_history = False

        # 拓扑图，初始默认全不连接
        self._tp_adjacency = np.zeros((self.MINER_NUM, self.MINER_NUM))
        self._graph = nx.Graph(self._tp_adjacency)
        self._network_histroy = []
        self._node_pos = None #后面由set_node_pos生成

        # 维护所有的活跃链路
        self._active_links:list[Link] = []

        self._dynamic = False
        self._tp_changes = []
        self._nextTpChangeRound=0
        self._avgTpChangeInterval=0
        self._edgeRemoveProb=0
        self._edgeAddProb=0
        self._maxPartitionsAllowed=0

        # status
        self._rcv_miners = defaultdict(list)
        self._routing_proc = defaultdict(list)
        self._stat_prop_times = {}
        self._block_num_bpt = []
        # 结果保存路径
        # NET_RESULT_PATH = global_var.get_net_result_path()
        # with open(NET_RESULT_PATH / 'routing_history.json', 'a+',  encoding='utf-8') as f:
        #     f.write('[')
        #     json.dump({"B0": {}}, f, indent=4)
        #     f.write(']')


    def set_net_param(self, init_mode = None, 
                      topology_path = None, 
                      ave_degree = None, 
                      bandwidth_honest = None, 
                      bandwidth_adv = None,
                      outage_prob = None, 
                      enable_resume_transfer = None,
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
        save_routing_graph (bool): Genarate routing graph at the end of simulation or not.
        show_label (bool): Show edge labels on network and routing graph or not. 
        '''
        if show_label is not None:
            self._show_label = show_label
        if bandwidth_honest is not None: # default 0.5 MB/round
            self._bandwidth_honest = bandwidth_honest 
        if bandwidth_adv is not None: # default 5 MB/round
            self._bandwidth_adv = bandwidth_adv 
        if topology_path is not None:
            self._topology_path = topology_path
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
            self._nextTpChangeRound += int(np.random.normal(self._avgTpChangeInterval, 
                                       0.2*self._avgTpChangeInterval))
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
  

    def access_network(self, new_msgs:list[Message|tuple[Message, int]], minerid:int, round:int, target:int,
                       sendTogether:bool = False):
        '''本轮新产生的消息添加到network_tape.

        param
        -----
        new_msg (list) : The newly generated message 
        minerid (int) : Miner_ID of the miner generated the message.
        round (int) : Current round. 
        ''' 
        if self.inv_handler(new_msgs):
            return
        for new_msg in new_msgs:
            rest_delay = new_msg[1] if isinstance(new_msg, tuple) else None
            msg = new_msg[0] if isinstance(new_msg, tuple) else new_msg
            if not self.message_preprocessing(msg):
                continue
            packet = TPPacket(msg, round, minerid, target)
            delay = self.cal_delay(msg, minerid, target) if rest_delay is None else rest_delay
            if rest_delay is not None:
                logger.info("round %d, M%d -> M%d, %s resume transfer delay %d", round, minerid, target, msg.name, rest_delay)
            link = Link(packet, delay, self)
            self._active_links.append(link)
            self._rcv_miners[link.get_block_msg_name()].append(minerid)
            # self.miners[minerid].receive(packet)
            # 这一条防止adversary集团的代表，自己没有接收到该消息
            logger.info("%s access network: M%d -> M%d, round %d", msg.name, minerid, target, round)
                
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
        '''计算sourceid和targetid之间的时延'''
        # 传输时延=消息大小除带宽 且传输时延至少1轮
        bw_mean = self._graph.edges[source, target]['bandwidth']
        bandwidth = np.random.normal(bw_mean,0.2*bw_mean)
        transmision_delay = math.ceil(msg.size / bandwidth)
        # 时延=处理时延+传输时延
        delay = self._miners[source]._NIC.processing_delay + transmision_delay
        return delay
    
    def diffuse(self, round):
        '''传播过程分为接收和转发两个过程'''
        self.forward_process(round)
        self.receive_process(round)
        if self._dynamic:
            self.topology_changing(round)
            
    def receive_process(self,round):
        """接收过程"""
        if len(self._active_links)==0:
            return
        dead_links = []
        # 传播完成，target接收数据包
        for i, link in enumerate(self._active_links):
            if link.delay > 0:
                link.delay -= 1
            if self.link_outage(round, link):
                dead_links.append(i)
                continue
            if link.delay > 0:
                continue
            link.target_miner()._NIC.nic_receive(link.packet)
            link.source_miner()._NIC.get_reply(round,link.get_block_msg_name(),link.target_id(), None)
            if self._rcv_miners[link.get_block_msg_name()][-1]!=-1:
                self._rcv_miners[link.get_block_msg_name()].append(link.target_id())
                self._routing_proc[link.get_block_msg_name()].append(
                    [{int(link.source_id()):link.packet.round}, {int(link.target_id()): round}]
                )
            self.stat_block_propagation_times(link.packet, round)
            dead_links.append(i)
        # 清理传播结束的link
        if len(dead_links) == 0:
            return
        self._active_links = [link for i, link in enumerate(self._active_links) 
                            if i not in dead_links]
        dead_links.clear()
    
    def forward_process(self, round):
        """转发过程"""
        for m in self._miners:
            m._NIC.nic_forward(round)

    def link_outage(self, round:int, link:Link):
        """每条链路都有概率中断"""
        if self._outage_prob <= 0:
            return False
        outage = False
        if link.delay == 0:
            return outage
        if random.uniform(0, 1) > self._outage_prob:
            return outage
        # 链路中断返回ERR_OUTAGE错误
        rest_delay = link.delay + 1 if self._enableResumeTransfer else None # 加1表示本轮失败重传
        link.source_miner()._NIC.get_reply(round, link.get_block_msg_name(), link.target_id(), ERR_OUTAGE, rest_delay)
        outage = True   
        return outage

    
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
        
        self._nextTpChangeRound += int(np.random.normal(self._avgTpChangeInterval, 
                                       0.2*self._avgTpChangeInterval))
        if changed:
            sub_nets = [[int(n) for n in sn] for sn in nx.connected_components(self._graph)]
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
        self._graph.remove_edge(node1, node2)
        sub_nets = nx.number_connected_components(self._graph)
        # isolates = nx.number_of_isolates(self._graph)
        isolates = 0
        # 若不允许产生分区但产生了分区，则重新连接
        if  sub_nets + isolates > self._maxPartitionsAllowed:
            self._graph.add_edge(node1, node2)
            bandwidths = {(node1,node2):(self._bandwidth_honest)}
            nx.set_edge_attributes(self._graph, bandwidths, "bandwidth")
            return removed
        
        self._miners[node1]._NIC.remove_neighbor(node2)
        self._miners[node2]._NIC.remove_neighbor(node1)
        removed = True

        # 记录下拓扑变更操作
        if "removes" not in list(change_op.keys()):
            change_op["removes"]=[[node1, node2]]
        else:
            change_op["removes"].append([node1, node2])
            
        remove_links = []
        for i, link in enumerate(self._active_links):
            if (((link.source_id(), link.target_id())==(node1,node2)) or 
                ((link.source_id(), link.target_id())==(node2,node1))):
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
        bandwidths = {(node1,node2):(self._bandwidth_honest)}
        nx.set_edge_attributes(self._graph, bandwidths, "bandwidth")
        self._miners[node1]._NIC.add_neighbor(node2, round)
        self._miners[node2]._NIC.add_neighbor(node1, round)
        # 记录下拓扑变更操作
        if "adds" not in list(change_op.keys()):
            change_op["adds"]=[[node1, node2]]
        else:
            change_op["adds"].append([node1, node2])
        return added


    def stat_block_propagation_times(self, packet: Packet, r):
        '''calculate the block propagation time'''
        if not isinstance(packet.payload, Message):
            return

        rn = len(set(self._rcv_miners[packet.payload.name]))
        mn = self.MINER_NUM

        def is_closest_to_percentage(a, b, percentage):
            return a == math.floor(b * percentage)

        rcv_rate = -1
        rcv_rates = [k for k in self._stat_prop_times.keys()]
        for p in rcv_rates:
            if is_closest_to_percentage(rn, mn, p):
                rcv_rate = p
                break
        if rcv_rate != -1 and rcv_rate in rcv_rates:
            if  self._rcv_miners[packet.payload.name][-1] != -1:
                self._stat_prop_times[rcv_rate] += r-packet.payload.blockhead.timestamp
                self._block_num_bpt[rcv_rates.index(rcv_rate)] += 1
                logger.debug(f"{packet.payload.name}:{rn},{rcv_rate} at round {r}")
            if rn == mn and self._rcv_miners[packet.payload.name][-1] != -1:
                self._rcv_miners[packet.payload.name].clear()
                self._rcv_miners[packet.payload.name].append(-1)
                self.save_specific_routing_process(packet.payload.name)
    
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
            if nx.number_connected_components(self._graph) != 1:
                if gen_net_approach != 'rand':
                    raise errors.NetIsoError('Brain-split in the newtork! ')
                retry_num = 10
                for _ in range(retry_num):
                    self.gen_network_rand(ave_degree, rand_mode)
                    if nx.number_connected_components(self._graph) == 1:
                        break
                if nx.number_connected_components(self._graph) == 1:
                    raise errors.NetIsoError(f'Brain-split in the newtork! '
                        f'Choose an appropriate degree, current: {ave_degree}')
                
            
            # 邻居节点保存到各miner的neighbor_list中
            for minerid in list(self._graph.nodes):
                self._miners[int(minerid)]._NIC._neighbors = \
                    list(self._graph.neighbors(int(minerid)))
            for miner in self._miners:
                miner._NIC.init_queues()
                
            # 结果展示和保存
            #print('adjacency_matrix: \n', self.tp_adjacency_matrix,'\n')
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
            self._graph = self.random_graph_with_fixed_degree(self.MINER_NUM, ave_degree)
        elif rand_mode == 'binomial':
            self._graph = nx.binomial_graph(self.MINER_NUM,
                                            ave_degree/(self.MINER_NUM-1))
        else:
            raise errors.NetGenError(f'Random network mode {rand_mode} is not supported!')
        # 防止出现孤立节点
        if nx.number_of_isolates(self._graph) > 0:
            iso_nodes = list(nx.isolates(self._graph))
            not_iso_nodes = [nd for nd in list(self._graph.nodes) if nd not in iso_nodes]
            targets = np.random.choice(not_iso_nodes, len(iso_nodes))
            for m1, m2 in zip(iso_nodes, targets):
                self._graph.add_edge(m1, m2)
        # 将攻击者集团的各个矿工相连
        for m1,m2 in itertools.combinations(range(self.MINER_NUM), 2):
            if self._miners[m1]._isAdversary and self._miners[m2]._isAdversary:
                if not self._graph.has_edge(m1, m2):
                    self._graph.add_edge(m1, m2)
        # 设置带宽（MB/round）
        bw_honest = self._bandwidth_honest
        bw_adv = self._bandwidth_adv
        bandwidths = {(u,v):(bw_adv if self._miners[u]._isAdversary
                      and self._miners[v]._isAdversary else bw_honest)
                      for u,v in self._graph.edges}
        nx.set_edge_attributes(self._graph, bandwidths, "bandwidth")
        self.tp_adjacency_matrix = nx.adjacency_matrix(self._graph).todense()


    def gen_network_by_adj(self):
        """
        如果读取邻接矩阵,则固定节点间的带宽0.5MB/round
        bandwidth单位:bit/round
        """
        # 读取csv文件的邻接矩阵
        self.read_adj_from_csv_undirected()
        # 根据邻接矩阵生成无向图
        self._graph = nx.Graph()
        # 生成节点
        self._graph.add_nodes_from([i for i in range(self.MINER_NUM)])
        # 生成边
        for m1 in range(len(self.tp_adjacency_matrix)): 
            for m2 in range(m1, len(self.tp_adjacency_matrix)):
                if self.tp_adjacency_matrix[m1, m2] == 1:
                    self._graph.add_edge(m1, m2)
        # 设置带宽（MB/round）
        bw_honest = self._bandwidth_honest
        bw_adv = self._bandwidth_adv
        bandwidths = {(u,v):(bw_adv if self._miners[u]._isAdversary
                      and self._miners[v]._isAdversary else bw_honest)
                      for u,v in self._graph.edges}
        nx.set_edge_attributes(self._graph, bandwidths, "bandwidth")
                    


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
        bw_arrary = np.array([float(eval(str(i))) for i in tp_coo_ndarray[2]])
        tp_bw_coo = sp.coo_matrix((bw_arrary, (row, col)), 
                                  shape=(self.MINER_NUM, self.MINER_NUM))
        adj_values = np.array([1 for _ in range(len(bw_arrary) * 2)])
        self.tp_adjacency_matrix = sp.coo_matrix(
            (adj_values, (np.hstack([row, col]), np.hstack([col, row]))),
            shape=(self.MINER_NUM, self.MINER_NUM)).todense()
        print('coo edges: \n', tp_bw_coo)
        self._graph.add_nodes_from([i for i in range(self.MINER_NUM)])
        for edge_idx, (src, tgt) in enumerate(zip(row, col)):
            self._graph.add_edge(src, tgt, bandwidth=bw_arrary[edge_idx])


    def read_adj_from_csv_undirected(self):
        """读取无向图的邻接矩阵adj"""
        # 读取csv文件并转化为ndarray类型,行是from 列是to
        csv_file = self._topology_path or 'conf/topologies/default_adj.csv'
        topology_ndarray  = pd.read_csv(csv_file, header=None, index_col=None).values
        # 判断邻接矩阵是否规范
        if np.isnan(topology_ndarray).any():
            raise errors.NetAdjError('无向图邻接矩阵不规范!(存在缺失)')
        if topology_ndarray.shape[0] != topology_ndarray.shape[1]:  # 不是方阵
            raise errors.NetAdjError('无向图邻接矩阵不规范!(row!=column)')
        if len(topology_ndarray) != self.MINER_NUM:  # 行数与环境定义的矿工数量不同
            raise errors.NetMinerNumError('矿工数量与环境定义不符!')
        if not np.array_equal(topology_ndarray, topology_ndarray.T):
            raise errors.NetAdjError('无向图邻接矩阵不规范!(不是对称阵)')
        if not np.all(np.diag(topology_ndarray) == 0):
            raise errors.NetAdjError('无向图邻接矩阵不规范!(对角元素不为0)')
        # 生成邻接矩阵
        self.tp_adjacency_matrix = np.zeros((len(topology_ndarray), len(topology_ndarray)))
        for i in range(len(topology_ndarray)):
            for j in range(i, len(topology_ndarray)):
                if topology_ndarray[i, j] != 0:
                    self.tp_adjacency_matrix[i, j] = self.tp_adjacency_matrix[j, i] = 1

    def save_network_attribute(self):
        '''保存网络参数'''
        network_attributes={
            'miner_num':self.MINER_NUM,
            'Generate Approach':self._init_mode,
            'Generate Edge Probability':self._ave_degree/self.MINER_NUM if self._init_mode == 'rand' else None,
            'Diameter':nx.diameter(self._graph),
            'Average Shortest Path Length':round(nx.average_shortest_path_length(self._graph), 3),
            'Degree Histogram': nx.degree_histogram(self._graph),
            "Average Degree": sum(dict(nx.degree(self._graph)).values())/len(self._graph.nodes),
            'Average Cluster Coefficient':round(nx.average_clustering(self._graph), 3),
            'Degree Assortativity':round(nx.degree_assortativity_coefficient(self._graph), 3),
        }
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
            if (((u, v) not in route_graph.edges) and 
                ((v, u) not in route_graph.edges)):
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
            arrows = False)
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

