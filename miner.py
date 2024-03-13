import logging
from collections import defaultdict
from dataclasses import dataclass

import global_var
from consensus import Consensus
from data import Block, Message
from external import I
from functions import for_name

# if TYPE_CHECKING:
from network import (
    ERR_OUTAGE,
    GetDataMsg,
    INVMsg,
    Network,
    Packet,
    TopologyNetwork,
    TPPacket,
)

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
        self.consensus:Consensus = for_name(
            global_var.get_consensus_type())(miner_id, consensus_params)# 共识
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
        self._output_queues = defaultdict(list[Message])
        self._channel_states = {}
        # 转发方式(拓扑网络)
        self._forward_strategy:str = FLOODING
        
        #保存矿工信息
        CHAIN_DATA_PATH=global_var.get_chain_data_path()
        with open(CHAIN_DATA_PATH / f'chain_data{str(self.miner_id)}.txt','a') as f:
            print(f"Miner {self.miner_id}\n"
                  f"consensus_params: {consensus_params}", file=f)
    
    def get_local_chain(self):
        return self.consensus.local_chain


    def join_network(self, network):
        """在环境初始化时加入网络"""
        self.network = network

        if len(self.neighbors) == 0:
            return
        
        # 初始化发送队列
        for neighbor in self.neighbors:
            self._output_queues[neighbor] = []
            self._channel_states[neighbor] = _IDLE
    
    def remove_neighbor(self, remove_id:int):
        """断开连接，从neighbor列表移除
        """
        if remove_id not in self.neighbors:
            logger.warning("M%d: removing neighbour M%d Failed! not connected", 
                           self.miner_id, remove_id)
            return
        self.neighbors = [n for n in self.neighbors if n != remove_id]
        
        if self._channel_states[remove_id] != _IDLE:
            self._output_queues[remove_id].insert(0, self._channel_states[remove_id])
        self._channel_states.pop(remove_id, None)
        logger.debug("M%d: removed neighbour M%d", self.miner_id, remove_id)

    def add_neighbor(self, add_id:int):
        if add_id in self.neighbors:
            logger.warning("M%d: adding neighbour M%d Failed! already connected", 
                           self.miner_id,add_id)
            return
        self.neighbors.append(add_id)
        self._channel_states[add_id] = _IDLE
        if add_id not in self._output_queues.keys():
            self._output_queues[add_id] = []
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
        for neighbor in self.neighbors:
            que = self._output_queues[neighbor]
            if len(que) == 0:
                continue
            
            # if len(que)!=len(set(que)):
            #     logger.warning("ERROR! round%d, M%d -> M%d, channel BUSY, sending %s, waiting %s,",
            #                 round, self.miner_id, neighbor, self._channel_states[neighbor].name ,
            #                 str([b.name for b in que if isinstance(b, Block)]))
            if self._channel_states[neighbor] != _IDLE:
                logger.info("round%d, M%d -> M%d, channel BUSY, sending %s, waiting %s",
                            round, self.miner_id, neighbor, self._channel_states[neighbor].name ,
                            str([b.name for b in que if isinstance(b, Block)]))
                continue
            while len(que) > 0:
                msg = que.pop(0)
                if isinstance(msg, Block):
                    # 发送前先发送inv消息询问是否需要该区块
                    targetRequire = self.inv_stub(round, neighbor, msg)
                    if not targetRequire:
                        continue
                    self._channel_states[neighbor] = msg
                self.send_data(round, [msg], neighbor)
                break
        
        self.consensus.clear_forward_tape()

    def inv_stub(self, round, target, block:Block):
        """
        在转发前发送inv消息，包含自己将要发送的区块
        """
        targetRequire = False
        inv = INVMsg(self.miner_id, target, block)
        getDataReply = GetDataMsg(require=False)
        # 发送的消息列表包含inv消息与期望的getDataReply，回应的getData会写入该Reply中
        self.network.access_network([inv, getDataReply], self.miner_id, target, round)
        if getDataReply.require is True:
            targetRequire = True
        return targetRequire
    

    def getdata_stub(self, inv:INVMsg):
        """
        接收到inv消息后，检查自己是否需要该区块，返回getData
        """
        getData = GetDataMsg(self.miner_id, inv.source, inv.block.name)
        getData.require = not self.consensus.is_in_local_chain(inv.block)
        return getData
    
    def send_data(self,round:int, msgs:list[Message], target:int):
        """
        inv没问题后发送数据
        """
        self.network.access_network(msgs, self.miner_id, target, round)

    def forward_block(self, block_msg:Block):
        """
        转发block，根据转发策略选择节点，加入到out_buffer中
        """
        if self._forward_strategy == FLOODING:
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
            self._output_queues[neighbor].append(block_msg)

    
    def get_reply(self, msg_name, target:int, err:str, round):
        """
        消息发送完成后，用于接收是否发送成功的回复
        """
        # 传输成功即将信道状态置为空闲
        if err is None:
            logger.info("round %d, M%d -> M%d: Forward  %s success!", 
                    round, self.miner_id, target, msg_name)
            self._channel_states[target]=_IDLE
            return
        # 信道中断将msg重新放回队列，等待下轮重新发送
        if err == ERR_OUTAGE:
            logger.info("round %d, M%d -> M%d: Forward  %s failed: link outage", 
                    round, self.miner_id, target, msg_name,)
            sending_msg = self._channel_states[target] 
            self._channel_states[target] = _IDLE
            self._output_queues[target].insert(0, sending_msg)
            return
        logger.error("round %d, M%d -> M%d: Forward  %s success!", 
                    round, self.miner_id, target, msg_name)
        


    def launch_consensus(self, input, round):
        '''开始共识过程\n
        return:
            new_msg 由共识类产生的新消息，没有就返回None type:list[Message]/None
            msg_available 如果有新的消息产生则为True type:Bool
        '''
        new_msgs, msg_available = self.consensus.consensus_process(
            self.isAdversary,input, round)
        return new_msgs, msg_available  # 返回挖出的区块，

    def BackboneProtocol(self, round):
        chain_update, update_index = self.consensus.maxvalid()
        input = I(round, self.input_tape)  # I function
        new_msgs, msg_available = self.launch_consensus(input, round)
        if new_msgs is not None and not isinstance(self.network, TopologyNetwork):
            self.network.access_network(new_msgs, self.miner_id, round)
            self.consensus._forward_tape.clear()
        if update_index or msg_available:
            
            return new_msgs
        return None  #  如果没有更新 返回空告诉environment回合结束
        
    
    def clear_tapes(self):
        # clear the input tape
        self.input_tape = []
        # clear the communication tape
        self.consensus._receive_tape = []
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

    l = []
    for i,ll in enumerate(l):
        print(i, "aaa")
    print("bbb")
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
    # times = {0.1: 15.855, 0.2: 24.407, 0.4: 38.181, 0.5: 43.493, 0.6: 47.188, 0.7: 51.855, 0.8: 56.784, 0.9: 64.741, 1.0: 76.12}
    # # times2 = {0.1: 16.589, 0.2: 27.906, 0.4: 43.926, 0.5: 52.578, 0.6: 56.212, 0.7: 63.647, 0.8: 73.141, 0.9: 80.889, 1.0: 105.342}
    # rcv_rates = list(times.keys())
    # t = list(times.values())
    # plt.plot(t,rcv_rates,"--o", label= "miner_num = 20, \nBW = 0.5MB/r, size = 8MB")
    # # rcv_rates = list(times2.keys())
    # # t = list(times2.values())
    # # plt.plot(t,rcv_rates,"--o", label= "miner_num = 20, \nBW = 0.5MB/r, size = 8MB with moving")
    # plt.xlabel("round")
    # plt.legend()
    # plt.grid()
    # plt.show()
