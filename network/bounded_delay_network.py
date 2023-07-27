import random
import logging
import math
from miner import Miner
from chain import Block
from .network_abc import Network

logger = logging.getLogger(__name__)

class BlockPacketBDNet(object):
    '''BoundedDelay网络中的区块数据包，包含路由相关信息'''
    def __init__(self, newblock: Block, minerid: int, round: int, rcvprob_start, outnetobj):
        self.block = newblock
        self.minerid = minerid
        self.round = round
        self.outnetobj = outnetobj  # 外部网络类实例
        # 传播过程相关
        self.received_miners = [minerid]
        # self.received_rounds = [round]
        self.trans_process_dict = {
            f'miner {minerid}': round
        }
        # 每次加self.rcvprob_inc
        self.recieve_prob = rcvprob_start

    def update_trans_process(self, minerid, round):
        # if a miner received the block update the trans_process
        self.received_miners.append(minerid)
        # self.received_rounds = [round]
        self.trans_process_dict.update({
            f'miner {minerid}': round
        })

class BoundedDelayNetwork(Network):
    """矿工以概率接收到区块，在特定轮数前必定所有矿工都收到区块"""

    def __init__(self, miners: list[Miner]):
        super().__init__()
        self.miners:list[Miner] = miners
        self.adv_miners:list[Miner] = [m for m in miners if m.isAdversary]
        self.network_tape:list[BlockPacketBDNet] = []
        self.rcvprob_start = 0.25
        self.rcvprob_inc = 0.25
        # status
        self.ave_block_propagation_times = {}
        self.block_num_bpt = []

    def set_net_param(self, rcvprob_start, rcvprob_inc, block_prop_times_statistic):
        """
        set the network parameters

        param
        ----- 
        rcvprob_start: 每个包进入网络时的接收概率,默认0.25
        rcvprob_inc: 之后每轮增加的接收概率,默认0.25
        """
        self.rcvprob_start = rcvprob_start
        self.rcvprob_inc = rcvprob_inc
        for rcv_rate in block_prop_times_statistic:
            self.ave_block_propagation_times.update({rcv_rate:0})
            self.block_num_bpt = [0 for _ in range(len(block_prop_times_statistic))]
        with open(self.NET_RESULT_PATH / 'network_attributes.txt', 'a') as f:
            print('Network Type: BoundedDelayNetwork', file=f)
            print(f'rcvprob_start:{self.rcvprob_start},rcvprob_inc={self.rcvprob_inc}', file=f)


    def is_recieved(self, rcvprob_th):
        """
        以均匀分布判断本轮是否接收

        param
        -----
        rcvprob_th: 接收的概率;
        """
        return random.uniform(0, 1) < rcvprob_th

    def access_network(self, newblock:Block, minerid:int, round:int):
        """
        Package the newblock and related information to network_tape.

        param
        -----
        newblock (Block) : The newly mined block 
        minerid (int) : Miner_ID of the miner generated the block. 
        round (int) : Current round. 

        """
        if not self.miners[minerid].isAdversary:
            block_packet = BlockPacketBDNet(newblock, minerid, round, 
                                        self.rcvprob_start, self)
            self.network_tape.append(block_packet)
    
        # 如果是攻击者发出的，攻击者集团的所有成员都在下一轮收到
        if self.miners[minerid].isAdversary:
            block_packet = BlockPacketBDNet(newblock, minerid, round, 
                                        self.rcvprob_start, self)
            for miner in [m for m in self.adv_miners if m.Miner_ID != minerid]:
                block_packet.update_trans_process(miner.Miner_ID, round)
                miner.receive_block(newblock)
            self.network_tape.append(block_packet)


    def diffuse(self, round):
        """Diffuse algorism for boundeddelay network"""
        # recieve_prob=0.7#设置接收概率，目前所有矿工概率一致
        # 随着轮数的增加，收到的概率越高，无限轮
        # 超过某轮后所有人收到
        # 一个人收到之后就不会再次收到这个块了
        if len(self.network_tape) > 0:
            died_packets = []
            for i, bp in enumerate(self.network_tape):
                not_rcv_miners = [m for m in self.miners \
                                if m.Miner_ID not in bp.received_miners]
                # 不会重复传给某个矿工
                for miner in not_rcv_miners:
                    if self.is_recieved(bp.recieve_prob):
                        bp.update_trans_process(miner.Miner_ID, round)
                        miner.receive_block(bp.block)
                        self.record_block_propagation_time(bp, round)
                        # 如果一个adv收到，其他adv也立即收到
                        if miner.isAdversary:
                            not_rcv_adv_miners = [m for m in self.adv_miners \
                                                if m.Miner_ID != miner.Miner_ID]
                            for adv_miner in not_rcv_adv_miners:
                                bp.update_trans_process(miner.Miner_ID, round)
                                adv_miner.receive_block(bp.block)
                                self.record_block_propagation_time(bp, round)
                # 更新recieve_prob
                if bp.recieve_prob < 1:
                    bp.recieve_prob += self.rcvprob_inc
                # 如果所有人都收到了，就丢弃该包
                if len(set(bp.received_miners)) == self.MINER_NUM:  
                    died_packets.append(i)
                    self.save_trans_process(bp)
            # 丢弃传播完成的包，更新network_tape
            self.network_tape = [n for i, n in enumerate(self.network_tape) \
                                    if i not in died_packets]
            died_packets = []



    def record_block_propagation_time(self, block_packet: BlockPacketBDNet, r):
        '''calculate the block propagation time'''
        bp = block_packet
        rn = len(set(bp.received_miners))
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
            logger.info(f"{bp.block.name}:{rn},{rcv_rate} at round {r}")
            self.ave_block_propagation_times[rcv_rate] += r-bp.round
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
        

    def save_trans_process(self, block_packet: BlockPacketBDNet):
        '''
        Save the transmission process of a specific block to network_log.txt
        '''
        bp = block_packet
        with open(self.NET_RESULT_PATH / 'network_log.txt', 'a') as f:
            result_str = f'{bp.block.name}:'+'\n'+'recieved miner in round'
            print(result_str, file=f)
            for miner_str,round in bp.trans_process_dict.items():
                print(' '*4, miner_str.ljust(10), ': ', round, file=f)