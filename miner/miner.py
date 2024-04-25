import logging

import global_var
from consensus import Consensus
from data import Block, Message
from external import I
from functions import for_name

# if TYPE_CHECKING:
from network import (
    AdHocNetwork,
    TopologyNetwork,
)

from ._consts import FLOODING, OUTER, SELF
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
            if (not self.isAdversary or 
                (self.isAdversary and global_var.get_attack_execute_type() != 'Eclipce')):
                self.forward([msg], OUTER)

        return rcvSuccess
    
       
    def forward(self, msgs, type, strategy:str=FLOODING, spec_targets:list = None):
        if type != SELF and type != OUTER:
            raise ValueError("Message type must be SELF or OUTER")
        
        for msg in msgs:
            # logger.info("M%d: forwarding %s", self.miner_id, msg.name)
            self.NIC.append_forward_buffer(msg, type, strategy, spec_targets)

    
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
    
        

