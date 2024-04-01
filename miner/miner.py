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

from ._consts import OUTER, SELF
from .network_interface import NetworkInterface, NICWithoutTp, NICWithTp

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
        self.round = -1
        #网络接口
        self.NIC:NetworkInterface =  None
        
        #保存矿工信息
        CHAIN_DATA_PATH=global_var.get_chain_data_path()
        with open(CHAIN_DATA_PATH / f'chain_data{str(self.miner_id)}.txt','a') as f:
            print(f"Miner {self.miner_id}\n"
                  f"consensus_params: {consensus_params}", file=f)
    
    def get_local_chain(self):
        return self.consensus.local_chain
    
    def in_local_chain(self, block:Block):
        return self.consensus.in_local_chain(block)


    def join_network(self, network):
        """初始化网络接口"""
        if (isinstance(network, TopologyNetwork) or 
            isinstance(network, AdHocNetwork)):
            self.NIC = NICWithTp(self)
        else:
            self.NIC = NICWithoutTp(self)
        if isinstance(network, AdHocNetwork):
            self.NIC.withSegments = True
        self.NIC.nic_join_network(network)
        
        
    def set_adversary(self, isAdversary:bool):
        '''
        设置是否为对手节点
        isAdversary=True为对手节点
        '''
        self.isAdversary = isAdversary
    
    
    def receive(self, msg: Message):
        '''处理接收到的消息，直接调用consensus.receive'''
        rcvSuccess = self.consensus.receive_filter(msg)
        if rcvSuccess:
            self.forward([msg], OUTER)
        return rcvSuccess
    
       
    def forward(self, msgs, type):
        if type != SELF and type != OUTER:
            raise ValueError("Message type must be SELF or OUTER")
        
        for msg in msgs:
            logger.info("M%d: forwarding %s", self.miner_id, msg.name)
            self.NIC.append_forward_buffer(msg, type)

    
    def launch_consensus(self, input, round):
        '''开始共识过程\n
        return:
            new_msg 由共识类产生的新消息，没有就返回None type:list[Message]/None
            msg_available 如果有新的消息产生则为True type:Bool
        '''
        new_msgs, msg_available = self.consensus.consensus_process(
            self.isAdversary,input, round)
        if new_msgs is not None:
            self.forward(new_msgs, SELF)
        return new_msgs, msg_available  # 返回挖出的区块，
        

    def BackboneProtocol(self, round):
        chain_update, update_index = self.consensus.local_state_update()
        input = I(round, self.input_tape)  # I function
        new_msgs, msg_available = self.launch_consensus(input, round)
        if update_index or msg_available:
            return new_msgs
        return None  #  如果没有更新 返回空告诉environment回合结束
        
    
    def clear_tapes(self):
        # clear the input tape
        self.input_tape = []
        # clear the communication tape
        self.consensus._receive_tape = []
        self.NIC._receive_buffer.clear()
        # self.NIC.clear_forward_buffer()
    
        
# if __name__ == "__main__":
#     import matplotlib.pyplot as plt

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
    # times = {0:0, 0.03: 5.457, 0.05: 6.925, 0.08: 9.141, 0.1: 10.099, 0.2: 12.218, 0.4: 15.21, 0.5: 16.257, 0.6: 17.259, 0.7: 18.206, 0.8: 19.479, 0.9: 21.204, 0.93: 21.776, 0.95: 22.362, 0.98: 23.81, 1.0: 25.875}
    # times2 = {0:0, 0.03: 0.944, 0.05: 1.804, 0.08: 2.767, 0.1: 3.308, 0.2: 5.421, 0.4: 8.797, 0.5: 10.396, 0.6: 12.071, 0.7: 13.956, 0.8: 16.217, 0.9: 19.377, 0.93: 20.777, 0.95: 21.971, 0.98: 24.683, 1.0: 29.027}
    # times3 ={0:0, 0.1: 1, 0.2: 2, 0.3:3, 0.4: 4, 0.5: 5.0, 0.6: 6.0, 0.7: 7.0, 0.8: 8.0, 0.9: 9.0, 1.0: 10} 
    # rcv_rates = list(times.keys())
    # t = list(times.values())
    # t = [tt/t[-1] for tt in t]
    # plt.plot(t,rcv_rates,"--o", label= "Topology Network")
    # rcv_rates = list(times2.keys())
    # t = list(times2.values())
    # t = [tt/t[-1] for tt in t]
    # plt.plot(t,rcv_rates,"--^", label= "Stochastic Propagation Network")
    # rcv_rates = list(times3.keys())
    # t = list(times3.values())
    # t = [tt/t[-1] for tt in t]
    # plt.plot(t,rcv_rates,"--*", label= "Deterministic Propagation Network")
    # plt.xlabel("Normalized number of rounds passed")
    # plt.ylabel("Ratio of received miners")
    # plt.legend()
    # plt.grid()
    # plt.show()
