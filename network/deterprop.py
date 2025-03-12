import copy
import logging
import math
import random
from typing import TYPE_CHECKING

import global_var
from data import Block, Message

if TYPE_CHECKING:   
    from miner.miner import Miner

from .network_abc import Network, Packet

logger = logging.getLogger(__name__)

class PacketPVNet(Packet):
    '''deterministic propagation网络中的数据包，包含路由相关信息'''
    def __init__(self, payload: Message, source_id: int, round: int, prop_vector:list, outnetobj):
        super().__init__(source_id, payload)
        self.round = round
        self.outnetobj = outnetobj  # 外部网络类实例
        # 传播过程记录
        self.received_miners:set[int] = set([source_id])
        self.trans_process = {f'miner {source_id}': round}
        # 每轮都pop第一个，记录剩余的传播向量
        self.remain_prop_vector = copy.deepcopy(prop_vector)

    def update_trans_process(self, minerid:int, round):
        # if a miner received the message update the trans_process
        self.received_miners.add(minerid)
        self.trans_process.update({f'miner {minerid}': round})

class DeterPropNetwork(Network):
    """依照传播向量,在每一轮中将消息传播给固定比例的矿工"""

    def __init__(self, miners):
        super().__init__()
        self.withTopology = False
        self.withSegments = False

        self.miners:list[Miner] = miners
        for m in self.miners:
            m._join_network(self)
        
        self.adv_miners:list[Miner] = None
        self.network_tape:list[PacketPVNet] = []
        self.prop_vector:list = [0.2, 0.4, 0.6, 0.8, 1.0] # 默认值

        # status
        self.ave_block_propagation_times = {}
        self.block_num_bpt = []

    def set_net_param(self, prop_vector:list=None):
        """
        set the network parameters

        param
        ----- 
        prop_vector: Propagation vector. 
                The elements represent 
                the rate of received miners when (1,2,3...) rounds  passed.
                The last element must be 1.0.

        """
        if prop_vector is  not None and prop_vector[len(prop_vector)-1] == 1:
            self.prop_vector = prop_vector
            self.target_percents = prop_vector
        self.adv_miners:list[Miner] = [m for m in self.miners if m._isAdversary]
        for rcv_rate in prop_vector:
            self.ave_block_propagation_times.update({rcv_rate:0})
            self.block_num_bpt = [0 for _ in range(len(prop_vector))]
        else:
            print(f"Use the default Propagation Vector:{self.prop_vector}")
        with open(self.NET_RESULT_PATH / 'network_attributes.txt', 'a') as f:
            print('Network Type: DeterPropNetwork', file=f)
            print(f'propagation_vector:{self.prop_vector}', file=f)


    def select_recieve_miners(self, packet:PacketPVNet):
        """选择本轮接收到该数据包的矿工

        param
        -----
        packet (PacketPVNet): 数据包

        Returns:
        -----
        rcv_miners(list): 本轮接收该数据包的矿工列表
        """
        rcv_miners:list[Miner] = []
        if len(packet.remain_prop_vector)>0:
            rcv_rate = packet.remain_prop_vector.pop(0)
            rcv_miner_num = round(rcv_rate * self.MINER_NUM)-len(packet.received_miners)
            if rcv_miner_num > 0:
                remain_miners = [m for m in self.miners
                                if m.miner_id not in packet.received_miners]
                rcv_miners = random.sample(remain_miners, rcv_miner_num)
        return rcv_miners

    def access_network(self, new_msg:list[Message], minerid:int, round:int,sendTogether:bool = False):
        """
        Package the new message and related information to network_tape.

        param
        -----
        new_msg (list) : The newly generated message 
        minerid (int) : Miner_ID of the miner generated the message.
        round (int) : Current round. 

        """
        for msg in new_msg:
            if not self.miners[minerid]._isAdversary:
                packet = PacketPVNet(msg, minerid, round, self.prop_vector, self)
                self.network_tape.append(packet)
        
            # 如果是攻击者发出的，攻击者集团的所有成员都在此时收到
            if self.miners[minerid]._isAdversary:
                packet = PacketPVNet(msg, minerid, round, self.prop_vector, self)
                for miner in [m for m in self.adv_miners if m.miner_id != minerid]:
                    packet.update_trans_process(miner.miner_id, round)
                    miner._NIC.nic_receive(packet)
                self.network_tape.append(packet)


    def diffuse(self, round):
        """Diffuse algorithm for `deterministic propagation network`.
        依照传播向量,在每一轮中将数据包传播给固定比例的矿工。

        param
        -----
        round (int): The current round in the Envrionment.
        """
        for m in self.miners:
            m._NIC.nic_forward(round)

        if len(self.network_tape) == 0:
            return
        died_packets = []
        for i, packet in enumerate(self.network_tape):
            rcv_miners = self.select_recieve_miners(packet)
            if len(rcv_miners) <= 0:
                continue
            for miner in rcv_miners:
                if miner.miner_id in packet.received_miners:
                    continue
                miner._NIC.nic_receive(packet)
                packet.update_trans_process(miner.miner_id, round)
                self.record_block_propagation_time(packet, round)
                # 如果一个adv收到，其他没收到的adv也立即收到
                if not miner._isAdversary:
                    continue
                not_rcv_advs = [m for m in self.adv_miners 
                                if m.miner_id != miner.miner_id]
                for adv_miner in not_rcv_advs:
                    adv_miner._NIC.nic_receive(packet)
                    packet.update_trans_process(adv_miner.miner_id, round)
                    self.record_block_propagation_time(packet, round)
            if len(packet.received_miners) == self.MINER_NUM:
                died_packets.append(i)
                if not global_var.get_compact_outputfile():
                    self.save_trans_process(packet)
        # 丢弃传播完成的包，更新network_tape
        self.network_tape = [n for i, n in enumerate(self.network_tape)
                            if i not in died_packets]
        died_packets = []

    
    def record_block_propagation_time(self, packet: PacketPVNet, r):
        '''calculate the block propagation time'''
        if not isinstance(packet.payload, Block):
            return

        rn = len(packet.received_miners)
        mn = self.MINER_NUM

        def is_closest_to_percentage(a, b, percentage):
            return a == math.floor(b * percentage)

        rcv_rate = -1
        rcv_rates = [k for k in self.ave_block_propagation_times.keys()]
        for p in rcv_rates:
            if is_closest_to_percentage(rn, mn, p):
                rcv_rate = p
                break
        if rcv_rate != -1 and rcv_rate in rcv_rates:
            logger.info(f"{packet.payload.name}:{rn},{rcv_rate} at round {r}")
            self.ave_block_propagation_times[rcv_rate] += r-packet.round
            self.block_num_bpt[rcv_rates.index(rcv_rate)] += 1

    def cal_block_propagation_times(self):
        rcv_rates = [k for k in self.ave_block_propagation_times.keys()]
        for i ,  rcv_rate in enumerate(rcv_rates):
            total_bpt = self.ave_block_propagation_times[rcv_rate ]
            total_num = self.block_num_bpt[i]
            if total_num == 0:
                continue
            self.ave_block_propagation_times[rcv_rate] = round(total_bpt/total_num, 3)
        return self.ave_block_propagation_times
        

    def save_trans_process(self, packet: PacketPVNet):
        '''
        Save the transmission process of a specific block to network_log.txt
        '''
        if isinstance(packet.payload, Block):
            with open(self.NET_RESULT_PATH / 'network_log.txt', 'a') as f:
                result_str = f'{packet.payload.name}:'+'\n'+'recieved miner in round'
                print(result_str, file=f)
                for miner_str,round in packet.trans_process.items():
                    print(' '*4, miner_str.ljust(10), ': ', round, file=f)

