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

class PacketBDNet(Packet):
    '''stochastic propagation 网络中的数据包，包含路由相关信息'''
    def __init__(self, payload, source_id: int, round: int, rcvprob_start, outnetobj):
        super().__init__(source_id, payload)
        self.round = round
        self.outnetobj = outnetobj  # 外部网络类实例
        # 传播过程相关
        self.received_miners:set[int] = set([source_id])
        # self.received_rounds = [round]
        self.trans_process_dict = {
            f'miner {source_id}': round
        }
        # 每次加self.rcvprob_inc
        self.recieve_prob = rcvprob_start

    def update_trans_process(self, minerid, round):
        # if a miner received the message update the trans_process
        self.received_miners.add(minerid)
        # self.received_rounds = [round]
        self.trans_process_dict.update({
            f'miner {minerid}': round
        })

class StochPropNetwork(Network):
    """矿工以概率接收到消息，在特定轮数前必定所有矿工都收到消息"""

    def __init__(self, miners):
        super().__init__()
        self.withTopology = False
        self.withSegments = False

        self.miners:list[Miner] = miners
        for m in self.miners:
            m._join_network(self)

        self.adv_miners:list[Miner] = None
        self.network_tape:list[PacketBDNet] = []
        self.rcvprob_start = 0.25
        self.rcvprob_inc = 0.25
        # status
        self.stat_prop_times = {}
        self.block_num_bpt = []

    def set_net_param(self, rcvprob_start, rcvprob_inc, stat_prop_times):
        """
        set the network parameters

        param
        ----- 
        rcvprob_start: 每个包进入网络时的接收概率,默认0.25
        rcvprob_inc: 之后每轮增加的接收概率,默认0.25
        """
        self.rcvprob_start = rcvprob_start
        self.rcvprob_inc = rcvprob_inc
        self.adv_miners:list[Miner] = [m for m in self.miners if m._isAdversary]
        for rcv_rate in stat_prop_times:
            self.stat_prop_times.update({rcv_rate:0})
            self.block_num_bpt = [0 for _ in range(len(stat_prop_times))]
        with open(self.NET_RESULT_PATH / 'network_attributes.txt', 'a') as f:
            print('Network Type: StochPropNetwork', file=f)
            print(f'rcvprob_start:{self.rcvprob_start},rcvprob_inc={self.rcvprob_inc}', file=f)


    def is_recieved(self, rcvprob_th):
        """
        以均匀分布判断本轮是否接收

        param
        -----
        rcvprob_th: 接收的概率;
        """
        return random.uniform(0, 1) < rcvprob_th

    def access_network(self, new_msg: list[Message], minerid:int, round:int,sendTogether:bool = False):
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
                packet = PacketBDNet(msg, minerid, round, self.rcvprob_start, self)
                self.network_tape.append(packet)
            else:
            # 如果是攻击者发出的，攻击者集团的所有成员都在下一轮收到
                packet = PacketBDNet(msg, minerid, round, 
                                    self.rcvprob_start, self)
                for miner in [m for m in self.adv_miners if m.miner_id != minerid]:
                    packet.update_trans_process(miner.miner_id, round)
                    miner._NIC.nic_receive(packet)
                self.network_tape.append(packet)


    def diffuse(self, round):
        """Diffuse algorithm for stochastic propagation network"""
        # recieve_prob=0.7#设置接收概率，目前所有矿工概率一致
        # 随着轮数的增加，收到的概率越高，无限轮
        # 超过某轮后所有人收到
        # 一个人收到之后就不会再次收到这个数据包了
        for m in self.miners:
            m._NIC.nic_forward(round)
        if len(self.network_tape)==0:
            return
        died_packets = []
        for i, packet in enumerate(self.network_tape):
            not_rcv_miners = [m for m in self.miners 
                            if m.miner_id not in packet.received_miners]
            # 不会重复传给某个矿工
            for miner in not_rcv_miners:
                if self.is_recieved(packet.recieve_prob):
                    packet.update_trans_process(miner.miner_id, round)
                    miner._NIC.nic_receive(packet)
                    self.record_block_propagation_time(packet, round)
                    # 如果一个adv收到，其他adv也立即收到
                    if not miner._isAdversary:
                        continue
                    not_rcv_adv_miners = [m for m in self.adv_miners
                                        if m.miner_id != miner.miner_id]
                    for adv_miner in not_rcv_adv_miners:
                        packet.update_trans_process(adv_miner.miner_id, round)
                        adv_miner._NIC.nic_receive(packet)
                        self.record_block_propagation_time(packet, round)
            # 更新recieve_prob
            if packet.recieve_prob < 1:
                packet.recieve_prob += self.rcvprob_inc
            # 如果所有人都收到了，就丢弃该包
            if len(packet.received_miners) == self.MINER_NUM:  
                died_packets.append(i)
                if not global_var.get_compact_outputfile():
                    self.save_trans_process(packet)
        # 丢弃传播完成的包，更新network_tape
        self.network_tape = [n for i, n in enumerate(self.network_tape) \
                                if i not in died_packets]
        died_packets = []

        



    def record_block_propagation_time(self, packet: PacketBDNet, r):
        '''calculate the block propagation time'''
        if not isinstance(packet.payload, Block):
            return

        rn = len(packet.received_miners)
        mn = self.MINER_NUM

        def is_closest_to_percentage(a, b, percentage):
            return a == math.floor(b * percentage)

        rcv_rate = -1
        rcv_rates = [k for k in self.stat_prop_times.keys()]
        for p in rcv_rates:
            if is_closest_to_percentage(rn, mn, p):
                rcv_rate = p
                break
        if rcv_rate != -1 and rcv_rate in rcv_rates:
            logger.info(f"{packet.payload.name}:{rn},{rcv_rate} at round {r}")
            self.stat_prop_times[rcv_rate] += r-packet.round
            self.block_num_bpt[rcv_rates.index(rcv_rate)] += 1

    def cal_block_propagation_times(self):
        rcv_rates = [k for k in self.stat_prop_times.keys()]
        for i ,  rcv_rate in enumerate(rcv_rates):
            total_bpt = self.stat_prop_times[rcv_rate ]
            total_num = self.block_num_bpt[i]
            if total_num == 0:
                continue
            self.stat_prop_times[rcv_rate] = round(total_bpt/total_num, 3)
        return self.stat_prop_times
        

    def save_trans_process(self, packet: PacketBDNet):
        '''
        Save the transmission process of a specific block to network_log.txt
        '''
        if isinstance(packet.payload,Block):
            with open(self.NET_RESULT_PATH / 'network_log.txt', 'a') as f:
                result_str = f'{packet.payload.name}:'+'\n'+'recieved miner in round'
                print(result_str, file=f)
                for miner_str,round in packet.trans_process_dict.items():
                    print(' '*4, miner_str.ljust(10), ': ', round, file=f)