import logging
import random
from collections import defaultdict

import global_var
from consensus import Consensus
from data import Block, Message
from external import I
from functions import for_name

# if TYPE_CHECKING:
from network import (
    ERR_OUTAGE,
    AdHocNetwork,
    GetDataMsg,
    INVMsg,
    Network,
    Packet,
    Segment,
    TopologyNetwork,
    TPPacket,
)

from .network_interface import NetworkInterface

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
        self._consensus:Consensus = for_name(
            global_var.get_consensus_type())(miner_id, consensus_params)# 共识
        #输入内容相关
        self.input_tape = []
        self.round = -1
        #网络相关
        self.NIC = NetworkInterface()
        self._network:Network = None
        self._neighbors:list[int] = []
        self.processing_delay=0    #处理时延

        # 暂存本轮收到的数据包(拓扑网络)
        self._receive_buffer:list[Packet]  = []
        self._segment_buffer = defaultdict(list[Message])

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
        return self._consensus.local_chain


    def join_network(self, network):
        """在环境初始化时加入网络"""
        self._network = network
        
        self.init_queues()
        
        
    def init_queues(self):
        if len(self._neighbors) == 0:
            return
        # 初始化发送队列
        for neighbor in self._neighbors:
            self._output_queues[neighbor] = []
            self._channel_states[neighbor] = _IDLE
    

    def remove_neighbor(self, remove_id:int):
        """断开连接，从neighbor列表移除
        """
        if remove_id not in self._neighbors:
            logger.warning("M%d: removing neighbour M%d Failed! not connected", 
                           self.miner_id, remove_id)
            return
        self._neighbors = [n for n in self._neighbors if n != remove_id]
    
        if isinstance(self._network, AdHocNetwork):
            self._output_queues.pop(remove_id, None)
            self._channel_states.pop(remove_id, None)
            return

        if self._channel_states[remove_id] != _IDLE:
            self._output_queues[remove_id].insert(0, self._channel_states[remove_id])
        self._channel_states.pop(remove_id, None)
        
        logger.info("M%d: removed neighbour M%d", self.miner_id, remove_id)

    def add_neighbor(self, add_id:int, round):
        if add_id in self._neighbors:
            logger.warning("M%d: adding neighbour M%d Failed! already connected", 
                           self.miner_id,add_id)
            return
        self._neighbors.append(add_id)
        self._channel_states[add_id] = _IDLE
        if add_id not in self._output_queues.keys():
            self._output_queues[add_id] = []
        inv = INVMsg(self.miner_id, add_id, self.get_local_chain().get_lastblock())
        self.forward_init(inv, add_id, round)
        logger.info("M%d: added neighbour M%d", self.miner_id, add_id)

    def set_adversary(self, isAdversary:bool):
        '''
        设置是否为对手节点
        isAdversary=True为对手节点
        '''
        self.isAdversary = isAdversary
    
    def in_local_chain(self, block:Block):
        return self._consensus.in_local_chain(block)

    def receive(self, packet: Packet):
        '''处理接收到的消息，直接调用consensus.receive'''
        rcv_msgs = self.NIC.get_receive_msgs()
        if len(rcv_msgs) == 0:
            return
        for msg in rcv_msgs:
            self._consensus.receive_filter(msg)
            self.NIC._forward_buffer.append(msg)
            self.NIC.receive_reply(msg)
       
        # return self._consensus.receive_filter(payload)
            
        # self._consensus.receive_filter(payload)

        # self._receive_buffer.append(packet)
        # payload = packet.payload
        # if not isinstance(payload, Segment):
        #     return self._consensus.receive_filter(payload)
        
        # if not isinstance(payload.msg, Block):
        #     raise TypeError("Segment not contains a block!")

        # segbuf_key = payload.msg.name
        # if self._consensus.in_local_chain(payload.msg):
        #     return False
        # self._segment_buffer[segbuf_key].append(payload.seg_id)
        # if len(set(self._segment_buffer[segbuf_key])) != payload.msg.segment_num:
        #     return False
        # self._segment_buffer.pop(segbuf_key)
        # logger.info("M%d: All %d segments of %s collected", self.miner_id, 
        #             payload.msg.segment_num, payload.msg.name )
        # return self._consensus.receive_filter(payload.msg)
        
    
    # def _get_segids_not_rcv(self, block:Block):
    #     seg_ids = self._segment_buffer[block.name]
    #     return [sid for sid in seg_ids if sid not in list(range(block.segment_num))]

    def forward(self, round:int):
        """根据消息类型选择转发策略"""
        
        

        forward_msgs = self._consensus.get_forward_tape()

        for msg in forward_msgs:
            if isinstance(msg, Block):
                self.forward_block(msg)
        
        # 从输出队列中取出待转发数据
        for neighbor in self._neighbors:
            que = self._output_queues[neighbor]
            if len(que) == 0:
                continue
            
            if self._channel_states[neighbor] != _IDLE:
                logger.info("round%d, M%d -> M%d, channel BUSY, sending %s, waiting %s",
                    round, self.miner_id, neighbor, self._channel_states[neighbor].name,
                    str([b.name for b in que if isinstance(b, Block)]))
                continue
            while len(que) > 0:
                msg = que.pop(0)
                if isinstance(msg, Block):
                    # 发送前先发送inv消息询问是否需要该区块
                    inv = INVMsg(self.miner_id, neighbor, msg)
                    getDataReply = self.inv_stub(inv, round)
                    if not getDataReply.require:
                        continue
                    self._channel_states[neighbor] = msg
                self.send_data([msg], neighbor, round)
                break
        
        self._consensus.clear_forward_tape()

    # def inv_stub(self, inv:INVMsg, round:int ):
    #     """
    #     在转发前发送inv消息，包含自己将要发送的区块
    #     """
    #     # 发送的消息列表包含inv消息与期望的getDataReply，
    #     # 回应的getData会写入该Reply中
    #     getDataReply = GetDataMsg(require=False)
    #     self._network.access_network(
    #         [inv, getDataReply], self.miner_id, inv.target, round)
    #     return getDataReply
    

    # def forward_adhoc(self,round):
    #     forward_msgs = self._consensus.get_forward_tape()

    #     for msg in forward_msgs:
    #         if msg != "inv":
    #             raise ValueError("Forward tape in Adhoc only accept \"inv\" ")
    #         targets = self.select_target_flooding()
    #         for target in  targets:
    #             self._output_queues[target].append("inv")
                
    #     for neighbor in self._neighbors:
    #         que = self._output_queues[neighbor]
    #         if len(que) == 0:
    #             continue
    #         msg = que.pop(0)
    #         if msg == "inv":
    #             inv = INVMsg(self.miner_id, neighbor, 
    #                          self.get_local_chain().get_lastblock())
    #             self.forward_init(inv, neighbor, round)
                
                
    #             while msg == "inv" and len(self._output_queues[neighbor]) != 0:
    #                 msg = self._output_queues[neighbor].pop(0)
                
    #             if msg == "inv" and len(self._output_queues[neighbor]) == 0:
    #                 continue
            
    #         self._channel_states[neighbor] = msg
    #         self.send_data([msg], neighbor, round)

    
    # def forward_init(self, inv:INVMsg, target:int, round:int):
    #     """在新建连接时先根据本地最新区块新建"""
    #     if inv.target != target:
    #         raise ValueError("Inv not match the target!")
        
    #     getDataReply  = self.inv_stub(inv, round)
    #     if not getDataReply.require:
    #         return
        
    #     if inv.target not in self._output_queues.keys():
    #         self._output_queues[inv.target] = []
    #     # 将需要的分段加入输出队列
    #     if isinstance(self._network, AdHocNetwork):
    #         for (req_b, segids) in getDataReply.req_segs:
    #             random.shuffle(segids)
    #             for sid in segids:
    #                 self._output_queues[inv.target].append(Segment(req_b, sid))
    #     # 将完整区块分段后加入输出队列
    #     for req_b in getDataReply.req_blocks:
    #         if isinstance(self._network, AdHocNetwork):
    #             segids = list(range(req_b.segment_num))
    #             random.shuffle(segids)
    #             for sid in segids:
    #                 self._output_queues[inv.target].append(Segment(req_b, sid))
    #         else:
    #             self._output_queues[inv.target].append(req_b)


    # def getdata_stub(self, inv:INVMsg):
    #     """
    #     接收到inv消息后，检查自己是否需要该区块，返回getData
    #     """
    #     getData = GetDataMsg(self.miner_id, inv.source, [inv.block])
    #     getData.require = not self._consensus.in_local_chain(inv.block)

    #     if isinstance(self._network, AdHocNetwork):
    #         # 返回需要的区块列表

    #         if getData.require is False:
    #             return getData
            
    #         getData.require = False
    #         # inv高度低于本地直接返回
    #         inv_h =  inv.block.get_height()
    #         loc_chain = self.get_local_chain()
    #         loc_h = loc_chain.get_lastblock().get_height()
    #         if inv_h < loc_h:
    #             return getData
    #         getData.require = True
    #         getData.req_blocks = []
    #         req_b = inv.block
    #         while not loc_chain.search(req_b) and req_b is not None:
    #             if req_b.name in self._segment_buffer.keys():
    #                 # 已经收到部分分段，请求需要的分段
    #                 sids_notrcv = self._get_segids_not_rcv(req_b)
    #                 getData.req_segs.append((req_b, sids_notrcv))
    #             else:
    #                 getData.req_blocks.append(req_b)
    #             req_b = req_b.last
    #     return getData
    
    # def send_data(self, msgs:list[Message], target:int,round:int):
    #     """
    #     inv没问题后发送数据
    #     """
    #     self._network.access_network(msgs, self.miner_id, target, round)


    # def forward_block(self, block_msg:Block):
    #     """
    #     转发block，根据转发策略选择节点，加入到out_buffer中
    #     """
    #     # 根据策略选择
    #     targets = []
    #     if self._forward_strategy == FLOODING:
    #         targets = self.select_target_flooding(block_msg)
        
    #     # 将区块加入target对应的队列中
    #     for target in targets:
    #         if target not in self._neighbors:
    #             logger.warning("Targets %s maynot be selected properly: neighbors %s", 
    #                            str(targets), str(self._neighbors))
    #             continue
    #         self._output_queues[target].append(block_msg)
            


    # def select_target_flooding(self, block_msg:Block=None):
    #     """
    #     泛洪转发，转发给不包括source的邻居节点
    #     """
    #     targets = []
    #     msg_from = -1
    #     if block_msg is not None:
    #         for packet in self._receive_buffer:
    #             if not isinstance(packet.payload, Block):
    #                 continue
    #             if block_msg.name == packet.payload.name:
    #                 msg_from = packet.source
    #                 break
        
    #     for neighbor in self._neighbors:
    #         if neighbor == msg_from:
    #             continue
    #         targets.append(neighbor)
    #     return targets

    
    # def get_reply(self, msg_name, target:int, err:str, round):
    #     """
    #     消息发送完成后，用于接收是否发送成功的回复
    #     """
    #     # 传输成功即将信道状态置为空闲
    #     if err is None:
    #         logger.info("round %d, M%d -> M%d: Forward  %s success!", 
    #                 round, self.miner_id, target, msg_name)
    #         self._channel_states[target]=_IDLE
    #         return
    #     # 信道中断将msg重新放回队列，等待下轮重新发送
    #     if err == ERR_OUTAGE:
    #         logger.info("round %d, M%d -> M%d: Forward  %s failed: link outage", 
    #                 round, self.miner_id, target, msg_name,)
    #         sending_msg = self._channel_states[target] 
    #         self._channel_states[target] = _IDLE
    #         self._output_queues[target].insert(0, sending_msg)
    #         return
    #     logger.error("round %d, M%d -> M%d: Forward  %s unkonwn ERR!", 
    #                 round, self.miner_id, target, msg_name)
        


    # def launch_consensus(self, input, round):
    #     '''开始共识过程\n
    #     return:
    #         new_msg 由共识类产生的新消息，没有就返回None type:list[Message]/None
    #         msg_available 如果有新的消息产生则为True type:Bool
    #     '''
    #     new_msgs, msg_available = self._consensus.consensus_process(
    #         self.isAdversary,input, round)
    #     return new_msgs, msg_available  # 返回挖出的区块，

    def BackboneProtocol(self, round):
        self.receive()
        chain_update, update_index = self._consensus.maxvalid()
        input = I(round, self.input_tape)  # I function
        new_msgs, msg_available = self.launch_consensus(input, round)
        if (new_msgs is not None and not isinstance(self._network, TopologyNetwork)
            and not isinstance(self._network, AdHocNetwork)):
            self._network.access_network(new_msgs, self.miner_id, round)
            self._consensus._forward_tape.clear()
        if update_index or msg_available:
            
            return new_msgs
        return None  #  如果没有更新 返回空告诉environment回合结束
        
    
    def clear_tapes(self):
        # clear the input tape
        self.input_tape = []
        # clear the communication tape
        self._consensus._receive_tape = []
        self._receive_buffer.clear()
        
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

#     l = []
#     for i,ll in enumerate(l):
#         print(i, "aaa")
#     print("bbb")
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
    times = {0:0, 0.03: 5.457, 0.05: 6.925, 0.08: 9.141, 0.1: 10.099, 0.2: 12.218, 0.4: 15.21, 0.5: 16.257, 0.6: 17.259, 0.7: 18.206, 0.8: 19.479, 0.9: 21.204, 0.93: 21.776, 0.95: 22.362, 0.98: 23.81, 1.0: 25.875}
    times2 = {0:0, 0.03: 0.944, 0.05: 1.804, 0.08: 2.767, 0.1: 3.308, 0.2: 5.421, 0.4: 8.797, 0.5: 10.396, 0.6: 12.071, 0.7: 13.956, 0.8: 16.217, 0.9: 19.377, 0.93: 20.777, 0.95: 21.971, 0.98: 24.683, 1.0: 29.027}
    times3 ={0:0, 0.1: 1, 0.2: 2, 0.3:3, 0.4: 4, 0.5: 5.0, 0.6: 6.0, 0.7: 7.0, 0.8: 8.0, 0.9: 9.0, 1.0: 10} 
    rcv_rates = list(times.keys())
    t = list(times.values())
    t = [tt/t[-1] for tt in t]
    plt.plot(t,rcv_rates,"--o", label= "Topology Network")
    rcv_rates = list(times2.keys())
    t = list(times2.values())
    t = [tt/t[-1] for tt in t]
    plt.plot(t,rcv_rates,"--^", label= "Stochastic Propagation Network")
    rcv_rates = list(times3.keys())
    t = list(times3.values())
    t = [tt/t[-1] for tt in t]
    plt.plot(t,rcv_rates,"--*", label= "Deterministic Propagation Network")
    plt.xlabel("Normalized number of rounds passed")
    plt.ylabel("Ratio of received miners")
    plt.legend()
    plt.grid()
    plt.show()
