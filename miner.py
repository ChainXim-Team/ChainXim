import logging
from collections import defaultdict

import global_var
from consensus import Consensus
from data import Block, Message
from external import I
from functions import for_name

# if TYPE_CHECKING:
from network import Network, Packet, TPPacket

FLOODING = "Flooding"


# 发送队列状态
_BUSY = "busy"
_IDLE = "idle"


logger = logging.getLogger(__name__)


class Miner(object):
    def __init__(self, miner_id, consensus_params:dict):
        self.miner_id = miner_id #矿工ID
        self.isAdversary = False
        #共识相关
        self.consensus:Consensus = \
            for_name(global_var.get_consensus_type())(miner_id, consensus_params)# 共识
        #输入内容相关
        self.input_tape = []
        #网络相关
        # self.NIC = NetworkInterface()
        self.network:Network = None
        self.neighbors:list[int] = []
        self.processing_delay=0    #处理时延

        # 暂存本轮收到的数据包(拓扑网络)
        self.receive_buffer:list[TPPacket]  = []

        # 输出队列(拓扑网络)
        self.output_queues = defaultdict(list[Message])
        self.channel_states = {}
        # 转发方式(拓扑网络)
        self.forward_strategy:str = FLOODING
        
        #保存矿工信息
        CHAIN_DATA_PATH=global_var.get_chain_data_path()
        with open(CHAIN_DATA_PATH / f'chain_data{str(self.miner_id)}.txt','a') as f:
            print(f"Miner {self.miner_id}\n"
                  f"consensus_params: {consensus_params}", file=f)

    def join_network(self, network):
        """在环境初始化时加入网络"""
        self.network = network

        if len(self.neighbors) == 0:
            return
        
        # 初始化发送队列
        for neighbor in self.neighbors:
            self.output_queues[neighbor] = []
            self.channel_states[neighbor] = _IDLE
    
    def remove_neighbor(self, remove_id:int):
        if remove_id not in self.neighbors:
            logger.warning("M%d: removing neighbour M%d Failed! not connected", 
                           self.miner_id, remove_id)
            return
        self.neighbors = [n for n in self.neighbors if n != remove_id]
        self.channel_states.pop(remove_id, None)
        self.output_queues.pop(remove_id, None)
        logger.debug("M%d: removed neighbour M%d", self.miner_id, remove_id)

    def add_neighbor(self, add_id:int):
        if add_id in self.neighbors:
            logger.warning("M%d: adding neighbour M%d Failed! already connected", 
                           self.miner_id,add_id)
            return
        self.neighbors.append(add_id)
        self.channel_states[add_id] = _IDLE
        self.output_queues[add_id] = []
        logger.debug("M%d: added neighbour M%d", self.miner_id, add_id)

    def set_adversary(self, isAdversary:bool):
        '''
        设置是否为对手节点
        isAdversary=True为对手节点
        '''
        self.isAdversary = isAdversary

    def receive(self, packet: Packet):
        '''处理接收到的消息，直接调用consensus.receive'''
        if isinstance(packet, TPPacket):
            self.receive_buffer.append(packet)
        return self.consensus.receive_filter(packet.payload)
    

    def forward(self, round:int):
        """根据消息类型选择转发策略"""
        forward_msgs = self.consensus.get_forward_tape()
        for msg in forward_msgs:
            if isinstance(msg, Block):
                self.forward_block(msg)
        
        # 从输出队列中取出待转发数据
        for neighbor, que in self.output_queues.items():
            if len(que) == 0:
                continue
            if len(que)!=len(set(que)):
                logger.info("ERROR! round%d, M%d -> M%d, channel BUSY, sending %s, waiting %s",
                            round, self.miner_id, neighbor, self.channel_states[neighbor] ,
                            str([b.name for b in que if isinstance(b, Block)]))
            if self.channel_states[neighbor] != _IDLE:
                logger.info("round%d, M%d -> M%d, channel BUSY, sending %s, waiting %s",
                            round, self.miner_id, neighbor, self.channel_states[neighbor] ,
                            str([b.name for b in que if isinstance(b, Block)]))
                continue
            msg = que.pop(0)
            if isinstance(msg, Block):
                self.channel_states[neighbor] = msg.name
            self.network.access_network([msg], self.miner_id, neighbor, round)

        self.consensus.clear_forward_tape()

    def forward_block(self, block_msg:Block):
        """
        转发block，根据转发策略选择节点，加入到out_buffer中
        """
        if self.forward_strategy == FLOODING:
            self.forward_block_flooding(block_msg)


    def forward_block_flooding(self, block_msg:Block):
        """
        泛洪转发，转发给不包括source的邻居节点
        """
        msg_from = -1
        for packet in self.receive_buffer:
            if not isinstance(packet.payload, Block):
                continue
            if block_msg.name == packet.payload.name:
                msg_from = packet.source
                break

        for neighbor in self.neighbors:
            if neighbor == msg_from:
                continue
            self.output_queues[neighbor].append(block_msg)

    
    def get_reply(self, msg_name, target:int, success:bool, round):
        """
        在网络发送完成后，回复是否发送成功
        """
        if not success:
            logger.warning("round %d, M%d -> M%d: Forward %s failed!", 
                           round, self.miner_id, target, msg_name)
            self.channel_states[target]=_IDLE
            return
        logger.info("round %d, M%d -> M%d: Forward  %s success!", 
                    round, self.miner_id, target, msg_name)
        self.channel_states[target]=_IDLE


    def launch_consensus(self, input, round):
        '''开始共识过程\n
        return:
            new_msg 由共识类产生的新消息，没有就返回None type:list[Message]/None
            msg_available 如果有新的消息产生则为True type:Bool
        '''
        new_msg, msg_available = self.consensus.consensus_process(
            self.isAdversary,input, round)
        return new_msg, msg_available  # 返回挖出的区块，

    def BackboneProtocol(self, round):
        chain_update, update_index = self.consensus.maxvalid()
        input = I(round, self.input_tape)  # I function
        new_msg, msg_available = self.launch_consensus(input, round)
        if update_index or msg_available:
            return new_msg
        else:
            return None  #  如果没有更新 返回空告诉environment回合结束
        
    
    def clear_states(self):
        # clear the input tape
        self.input_tape = []
        # clear the communication tape
        self.consensus.receive_tape = []
        self.receive_buffer.clear()
        
    # def ValiChain(self, blockchain: Chain = None):
    #     '''
    #     检查是否满足共识机制\n
    #     相当于原文的validate
    #     输入:
    #         blockchain 要检验的区块链 type:Chain
    #         若无输入,则检验矿工自己的区块链
    #     输出:
    #         IsValid 检验成功标识 type:bool
    #     '''
    #     if blockchain is None:#如果没有指定链则检查自己
    #         IsValid=self.consensus.valid_chain(self.Blockchain.lastblock)
    #         if IsValid:
    #             print('Miner', self.Miner_ID, 'self_blockchain validated\n')
    #         else:
    #             print('Miner', self.Miner_ID, 'self_blockchain wrong\n')
    #     else:
    #         IsValid = self.consensus.valid_chain(blockchain)
    #         if not IsValid:
    #             print('blockchain wrong\n')
    #     return IsValid
        
if __name__ == "__main__":
    import matplotlib.pyplot as plt
    # aa= defaultdict(lambda : True)

    # neighbors = [1,3,5,7,11]
    # output_queue=defaultdict(list)
    # channel_states = {}

    # for neighbor in neighbors:
    #     output_queue[neighbor] = []
    #     channel_states[neighbor] = _IDLE
    # # if not  aa[2]:
    # output_queue[1].append(1)
    # print(output_queue, channel_states)
    # if __name__ == "__main__":
    times = {0.1: 15.224, 0.2: 23.423, 0.4: 34.19, 0.5: 36.551, 0.6: 41.819, 0.7: 44.75, 0.8: 50.167, 0.9: 54.199, 1.0: 61.553}
    rcv_rates = list(times.keys())
    t = list(times.values())
    plt.plot(t,rcv_rates,"--o", label= "miner_num = 20, degree = 4.1, BW = 0.5MB/r")
    plt.legend()
    plt.grid()
    plt.show()
