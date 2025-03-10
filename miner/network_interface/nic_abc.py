from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from data import Block, Message
from network import (
    INVMsg,
    Network,
    Packet,
)

if TYPE_CHECKING:
    from .. import Miner

from .._consts import FLOODING, OUTER_RCV_MSG, SELF_GEN_MSG, SYNC_LOC_CHAIN


class NetworkInterface(metaclass=ABCMeta):
    def __init__(self, miner) -> None:
        self.processing_delay=0
        
        self.miner:Miner = miner
        self.miner_id = self.miner.miner_id
        self._network:Network = None
        self._receive_buffer:list[Packet]  = []
        self._forward_buffer:dict[str, list[Block]] = {OUTER_RCV_MSG:[],SELF_GEN_MSG:[]}

        self.inv_count = 0
        self.sync_full_chain_count = 0
        self.send_data_count = 0
    
    def clear_forward_buffer(self):
        self._forward_buffer[OUTER_RCV_MSG].clear()
        self._forward_buffer[SELF_GEN_MSG].clear()
     
    def append_forward_buffer(self, msg:Message, msg_source_type:str, forward_strategy: str = FLOODING, 
                              spec_target:list = None, syncLocalChain = False):
        """
        将要转发的消息添加到_forward_buffer中。(唯一暴露给miner的接口)
        """
        if msg_source_type != SELF_GEN_MSG and msg_source_type != OUTER_RCV_MSG:
            raise ValueError("Message source type must be SELF_GEN_MSG or OUTER_RCV_MSG")
        if msg_source_type == SELF_GEN_MSG:
            if self._network.withTopology and syncLocalChain:
                msg = SYNC_LOC_CHAIN
            self._forward_buffer[SELF_GEN_MSG].append([msg, forward_strategy, spec_target])
            if (not self._network.withTopology and len(self._forward_buffer[SELF_GEN_MSG]) > 1 
                and not self.miner._isAdversary):
                raise ValueError("Each round, a miner can only put one message into the network.")
        elif msg_source_type == OUTER_RCV_MSG:
            self._forward_buffer[OUTER_RCV_MSG].append([msg, forward_strategy, spec_target])
    
    @abstractmethod
    def nic_join_network(self, network):
        """在环境初始化时加入网络"""
        self._network = network

    @abstractmethod
    def nic_receive(self, packet: Packet):
        ...

    @abstractmethod
    def nic_forward(self, round:int):
        ...

    """下面只有nic_with_tp要实现"""
    @abstractmethod
    def get_reply(self, cur_round:int, msg_name:str, target:int, err:str, rest_delay:int):
        ...
    @abstractmethod
    def remove_neighbor(self, remove_id:int):
        ...
    @abstractmethod
    def add_neighbor(self, add_id:int, round):
        ...
    @abstractmethod
    def reply_getdata(self, inv:INVMsg):
        ...