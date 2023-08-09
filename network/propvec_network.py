import random
import logging
import copy
import math
from miner import Miner
from chain import Block
from .network_abc import Network

logger = logging.getLogger(__name__)

class BlockPacketPVNet(object):
    '''propagation vector网络中的区块数据包，包含路由相关信息'''
    def __init__(self, newblock: Block, minerid: int, round: int, prop_vector:list, outnetobj):
        self.block = newblock
        self.minerid = minerid
        self.round = round
        self.outnetobj = outnetobj  # 外部网络类实例
        # 传播过程相关
        self.received_miners:list[int] = [minerid]
        self.trans_process_dict = {
            f'miner {minerid}': round
        }
        # 每轮都pop第一个，记录剩余的传播向量
        self.remain_prop_vector = copy.deepcopy(prop_vector)

    def update_trans_process(self, minerid:int, round):
        # if a miner received the block update the trans_process
        self.received_miners.append(minerid)
        self.trans_process_dict.update({
            f'miner {minerid}': round
        })

class PropVecNetwork(Network):
    """依照传播向量,在每一轮中将区块传播给固定比例的矿工"""

    def __init__(self, miners: list[Miner]):
        super().__init__()
        self.miners:list[Miner] = miners
        self.adv_miners:list[Miner] = [m for m in miners if m.isAdversary]
        self.network_tape:list[BlockPacketPVNet] = []
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
                the rate of received miners when (0,1,2,3...) rounds  passed.
                The last element must be 1.0.

        """
        if prop_vector is  not None and prop_vector[len(prop_vector)-1] == 1:
            self.prop_vector = prop_vector
            self.target_percents = prop_vector
        for rcv_rate in prop_vector:
            self.ave_block_propagation_times.update({rcv_rate:0})
            self.block_num_bpt = [0 for _ in range(len(prop_vector))]
        else:
            print(f"Use the default Propagation Vector:{self.prop_vector}")
        with open(self.NET_RESULT_PATH / 'network_attributes.txt', 'a') as f:
            print('Network Type: PropVecNetwork', file=f)
            print(f'propagation_vector:{self.prop_vector}', file=f)


    def select_recieve_miners(self, block_packet:BlockPacketPVNet):
        """选择本轮接收到该区块的矿工

        param
        -----
        block_packet (BlockPacketPVNet): 区块数据包

        Returns:
        -----
        rcv_miners(list): 本轮接收该区块的矿工列表
        """
        bp = block_packet
        rcv_miners:list[Miner] = []
        if len(bp.remain_prop_vector)>0:
            rcv_rate = bp.remain_prop_vector.pop(0)
            rcv_miner_num = round(rcv_rate * self.MINER_NUM)-len(bp.received_miners)
            if rcv_miner_num > 0:
                remain_miners = [m for m in self.miners \
                                if m.Miner_ID not in bp.received_miners]
                rcv_miners = random.sample(remain_miners, rcv_miner_num)
        return rcv_miners

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
            block_packet = BlockPacketPVNet(newblock, minerid, round, 
                                        self.prop_vector, self)
            self.network_tape.append(block_packet)
    
        # 如果是攻击者发出的，攻击者集团的所有成员都在此时收到
        if self.miners[minerid].isAdversary:
            block_packet = BlockPacketPVNet(newblock, minerid, round, 
                                        self.prop_vector, self)
            for miner in [m for m in self.adv_miners if m.Miner_ID != minerid]:
                block_packet.update_trans_process(miner.Miner_ID, round)
                miner.consensus.receive_block(newblock)
            self.network_tape.append(block_packet)


    def diffuse(self, round):
        """Diffuse algorism for `propagation vector network`.
        依照传播向量,在每一轮中将区块传播给固定比例的矿工。

        param
        -----
        round (int): The current round in the Envrionment.
        """
        if len(self.network_tape) > 0:
            died_packets = []
            for bp_idx, bp in enumerate(self.network_tape):
                rcv_miners = self.select_recieve_miners(bp)
                if len(rcv_miners) > 0:
                    for miner in rcv_miners:
                        miner.consensus.receive_block(bp.block)
                        bp.update_trans_process(miner.Miner_ID, round)
                        self.record_block_propagation_time(bp, round)
                        # 如果一个adv收到，其他没收到的adv也立即收到
                        if not miner.isAdversary:
                            not_rcv_adv_miners = [m for m in self.adv_miners \
                                                if m.Miner_ID != miner.Miner_ID]
                            for adv_miner in not_rcv_adv_miners:
                                if adv_miner.Miner_ID not in bp.received_miners:
                                    adv_miner.consensus.receive_block(bp.block)
                                    bp.update_trans_process(miner.Miner_ID, round)
                                    self.record_block_propagation_time(bp, round)
                if len(set(bp.received_miners)) == self.MINER_NUM:
                    died_packets.append(bp_idx)
                    self.save_trans_process(bp)
            # 丢弃传播完成的包，更新network_tape
            self.network_tape = [n for i, n in enumerate(self.network_tape) \
                                    if i not in died_packets]
            died_packets = []


    
    def record_block_propagation_time(self, block_packet: BlockPacketPVNet, r):
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
        

    def save_trans_process(self, block_packet: BlockPacketPVNet):
        '''
        Save the transmission process of a specific block to network_log.txt
        '''
        bp = block_packet
        with open(self.NET_RESULT_PATH / 'network_log.txt', 'a') as f:
            result_str = f'{bp.block.name}:'+'\n'+'recieved miner in round'
            print(result_str, file=f)
            for miner_str,round in bp.trans_process_dict.items():
                print(' '*4, miner_str.ljust(10), ': ', round, file=f)
