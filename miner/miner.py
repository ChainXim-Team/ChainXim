import logging
from array import array

import global_var
from consensus import Consensus
from data import Block, Message
from external import I
from functions import for_name

from ._consts import FLOODING, OUTER_RCV_MSG, SELF_GEN_MSG, SYNC_LOC_CHAIN
from .network_interface import NetworkInterface, NICWithoutTp, NICWithTp

logger = logging.getLogger(__name__)


class Miner(object):
    def __init__(self, miner_id, consensus_params:dict, max_block_capacity:int = 0, disable_dataitem_queue=False):
        self.miner_id = miner_id #矿工ID
        self._isAdversary = False
        #共识相关
        self.consensus:Consensus = for_name(
            global_var.get_consensus_type())(miner_id, consensus_params)# 共识
        #输入内容相关
        self.input_tape = []
        self.round = -1
        #网络接口
        self._NIC:NetworkInterface =  None
        self.__auto_forwarding = True
        self.receive_history = dict()
        # maximum data items in a block
        self.max_block_capacity = max_block_capacity
        if self.max_block_capacity > 0 and not disable_dataitem_queue:
            self.dataitem_queue = array('Q')
        #保存矿工信息
        CHAIN_DATA_PATH=global_var.get_chain_data_path()
        with open(CHAIN_DATA_PATH / f'chain_data{str(self.miner_id)}.txt','a') as f:
            print(f"Miner {self.miner_id}\n"
                  f"consensus_params: {consensus_params}", file=f)
    
    def get_local_chain(self):
        return self.consensus.local_chain
    
    def in_local_chain(self, block:Block):
        return self.consensus.in_local_chain(block)

    def has_received(self, block:Message):
        return self.consensus.has_received(block)

    def _join_network(self, network):
        """初始化网络接口"""
        if network.withTopology:
            self._NIC = NICWithTp(self)
        else:
            self._NIC = NICWithoutTp(self)
        self._NIC.nic_join_network(network)
    
    @property
    def neighbors(self):
        return self._NIC._neighbors
        
    def set_adversary(self, _isAdversary:bool):
        '''
        设置是否为对手节点
        _isAdversary=True为对手节点
        '''
        self._isAdversary = _isAdversary
    
    def set_auto_forwarding(self, auto_forwarding:bool):
        '''
        设置是否自动转发消息
        auto_forwarding=True为自动转发
        '''
        self.__auto_forwarding = auto_forwarding

    def receive(self, source:int, msg: Message):
        '''处理接收到的消息，直接调用consensus.receive'''
        rcvSuccess = self.consensus.receive_filter(msg)
        if not rcvSuccess:
            return rcvSuccess
        else:
            self.receive_history[msg.name] = source
        if self.__auto_forwarding:
            self.forward([msg], OUTER_RCV_MSG)
        return rcvSuccess
    
       
    def forward(self, msgs:list[Message], msg_source_type, forward_strategy:str=FLOODING, 
                spec_targets:list=None, syncLocalChain = False):
        """将消息转发给其他节点

        args:
            msgs: list[Message] 需要转发的消息列表
            msg_source_type: str 消息来源类型, SELF_GEN_MSG表示由本矿工产生, OUTER_RCV_MSG表示由网络接收
            forward_strategy: str 消息转发策略
            spec_targets: list[int] 如果forward_strategy为SPECIFIC, 则spec_targets为转发的目标节点列表
            syncLocalChain: bool 是否向邻居同步本地链，尽量在产生新区块时同步
        
        """
        if msg_source_type != SELF_GEN_MSG and msg_source_type != OUTER_RCV_MSG:
            raise ValueError("Message type must be SELF or OUTER")
        logger.info("M%d: forwarding %s, type %s, strategy %s", self.miner_id, 
                    str([msg.name for msg in msgs] if len(msgs)>0 else [""]), msg_source_type, forward_strategy)
        for msg in msgs:
            self._NIC.append_forward_buffer(msg, msg_source_type, forward_strategy, spec_targets, syncLocalChain)

    
    def launch_consensus(self, input, round):
        '''开始共识过程

        return:
            new_msg 由共识类产生的新消息，没有就返回None type:list[Message]/None
            msg_available 如果有新的消息产生则为True type:Bool
        '''
        new_msgs, msg_available = self.consensus.consensus_process(
            self._isAdversary,input, round)
        if new_msgs is not None:
            # new_msgs.append(Message("testMsg", 1))
            self.forward(new_msgs, SELF_GEN_MSG, syncLocalChain = True)
        return new_msgs, msg_available  # 返回挖出的区块，
        

    def BackboneProtocol(self, round):
        _, chain_update = self.consensus.local_state_update()
        input = I(round, self.input_tape)  # I function
        if self.max_block_capacity > 0 and getattr(self, 'dataitem_queue', None) is not None:
            # exclude dataitems in updated blocks
            if len(chain_update) > 0:
                dataitem_exclude = set()
                for block in chain_update:
                    block:Consensus.Block
                    dataitem_exclude.update(array('Q', block.blockhead.content))
                self.dataitem_queue = array('Q', [x for x in self.dataitem_queue if x not in dataitem_exclude])
            self.dataitem_queue.frombytes(input)
            if len(self.dataitem_queue) > 10 * self.max_block_capacity:
                # drop the oldest data items if the queue is longer than 2 * max_block_capacity
                self.dataitem_queue.pop(0)
            input = self.dataitem_queue[:self.max_block_capacity].tobytes()

        new_msgs, msg_available = self.launch_consensus(input, round)

        if msg_available:
            # remove the data items in the new block from dataitem_queue
            if self.max_block_capacity > 0 and getattr(self, 'dataitem_queue', None) is not None:
                self.dataitem_queue = self.dataitem_queue[self.max_block_capacity:]
            return new_msgs
        return None  #  如果没有更新 返回空告诉environment回合结束
        
    
    def clear_tapes(self):
        # clear the input tape
        self.input_tape = []
        # clear the communication tape
        self.consensus.receive_tape = []
        self._NIC._receive_buffer.clear()
        # self._NIC.clear_forward_buffer()
    
        

