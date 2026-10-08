import logging
from typing import TYPE_CHECKING

import global_var
from data import Block, Message

if TYPE_CHECKING:   
    from miner.miner import Miner

from .network_abc import Network, Packet

logger = logging.getLogger(__name__)


class PacketWCBDNet(Packet):
    """WorstCaseBoundedDelay 网络中的数据包，包含路由相关信息"""
    def __init__(self, payload, source_id: int, round: int, outnetobj):
        super().__init__(source_id, payload)
        self.round = round
        self.outnetobj = outnetobj  # 外部网络类实例
        # 传播过程相关
        self.received_miners = [] if global_var.get_delayed_self_receive() else [source_id]
        self.trans_process_dict = {
            f'miner {source_id}': round
        }

    def update_trans_process(self, minerid, round):
        # if a miner received the message update the trans_process
        self.received_miners.append(minerid)
        self.trans_process_dict.update({
            f'miner {minerid}': round
        })


class WorstCaseBoundedDelayNetwork(Network):
    """
    最坏情况有界延迟网络：
    - 诚实矿工对任意消息的传播延迟固定为网络延迟上界 D（单位：轮次）
    - 攻击者集团内部传播延迟为 0（同一轮次内即同步）
    """
    def __init__(self, miners):
        super().__init__()
        self.miners:list[Miner] = miners
        for m in self.miners:
            m.join_network(self)
        self.adv_miners:list[Miner] = [m for m in miners if m.isAdversary]
        self.network_tape:list[PacketWCBDNet] = []

        # parameters
        self.delay_upper_bound:int = 1

        # stats
        self.stat_prop_times = {}
        self.block_num_bpt = []

    def set_net_param(self, delay_upper_bound:int, stat_prop_times=None):
        """
        设置网络参数

        param
        -----
        delay_upper_bound: 诚实方固定传播延迟上界（轮次）
        stat_prop_times: 可选，用于统计不同接收率下的传播时间。如果不需要统计，可以设置为 [] 或 None
        """
        self.delay_upper_bound = int(delay_upper_bound)
        if stat_prop_times is None:
            stat_prop_times = []
        for rcv_rate in stat_prop_times:
            self.stat_prop_times.update({rcv_rate:0})
            self.block_num_bpt = [0 for _ in range(len(stat_prop_times))]
        with open(self.NET_RESULT_PATH / 'network_attributes.txt', 'a') as f:
            print('Network Type: WorstCaseBoundedDelayNetwork', file=f)
            print(f'delay_upper_bound:{self.delay_upper_bound}', file=f)

    def access_network(self, new_msg: list[Message], minerid:int, round:int, target:int=None):
        """
        将新消息打包进入网络队列
        - 若消息由攻击者发出，则攻击者集团内其他成员在同一轮立即收到（0 延迟）
        """
        for msg in new_msg:
            packet = PacketWCBDNet(msg, minerid, round, self)
            if self.miners[minerid].isAdversary:
                # 攻击者内部 0 延迟
                for miner in [m for m in self.miners if m.isAdversary and m.miner_id != minerid]:
                    packet.update_trans_process(miner.miner_id, round)
                    miner.NIC.nic_receive(packet)
            self.network_tape.append(packet)

    def diffuse(self, round):
        """扩散算法：诚实矿工固定在发送轮 round0 + D 收到消息；攻击者立即收到所有消息（0延迟）"""
        for m in self.miners:
            m.NIC.nic_forward(round)
        if len(self.network_tape) == 0:
            return
        died_packets = []
        for i, packet in enumerate(self.network_tape):
            not_rcv_miners = [m for m in self.miners
                              if m.miner_id not in packet.received_miners]

            # 攻击者立即收到所有消息（0延迟），包括来自诚实矿工的消息
            # 注意：不能使用 self.adv_miners，因为网络初始化时攻击者还未被设定
            for miner in not_rcv_miners:
                if miner.isAdversary:
                    packet.update_trans_process(miner.miner_id, round)
                    miner.NIC.nic_receive(packet)
                    self.record_block_propagation_time(packet, round)

            # 到达固定延迟后，向尚未收到的诚实矿工投递
            if round >= packet.round + self.delay_upper_bound:
                for miner in not_rcv_miners:
                    if miner.miner_id not in packet.received_miners and not miner.isAdversary:
                        packet.update_trans_process(miner.miner_id, round)
                        miner.NIC.nic_receive(packet)
                        self.record_block_propagation_time(packet, round)

            # 如果所有人都收到了，就丢弃该包
            if len(set(packet.received_miners)) == self.MINER_NUM:
                died_packets.append(i)
                if not global_var.get_compact_outputfile():
                    self.save_trans_process(packet)
        # 移除传播完成的包
        self.network_tape = [n for i, n in enumerate(self.network_tape) if i not in died_packets]

    def record_block_propagation_time(self, packet: PacketWCBDNet, r):
        """统计区块传播时间（仅在 stat_prop_times 不为空时进行统计）"""
        if not isinstance(packet.payload, Block):
            return
        if len(self.stat_prop_times) == 0:
            return  # 如果未设置统计参数，直接返回
        rn = len(set(packet.received_miners))
        mn = self.MINER_NUM
        def is_closest_to_percentage(a, b, percentage):
            return a == math.floor(b * percentage)
        import math
        rcv_rate = -1
        rcv_rates = [k for k in self.stat_prop_times.keys()]
        for p in rcv_rates:
            if is_closest_to_percentage(rn, mn, p):
                rcv_rate = p
                break
        if rcv_rate != -1 and rcv_rate in rcv_rates:
            logger.info(f"{packet.payload.name}:{rn},{rcv_rate} at round {r}")
            self.stat_prop_times[rcv_rate] += r - packet.round
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
        
    def save_trans_process(self, packet: PacketWCBDNet):
        """保存特定区块的传播过程到 network_log.txt"""
        if isinstance(packet.payload,Block):
            with open(self.NET_RESULT_PATH / 'network_log.txt', 'a') as f:
                result_str = f'{packet.payload.name}:'+'\n'+'recieved miner in round'
                print(result_str, file=f)
                for miner_str,round in packet.trans_process_dict.items():
                    print(' '*4, miner_str.ljust(10), ': ', round, file=f)



