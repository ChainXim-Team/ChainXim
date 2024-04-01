from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from data import Block, Message
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

if TYPE_CHECKING:
    from .. import Miner

from .._consts import OUTER, SELF


class NetworkInterface(metaclass=ABCMeta):
    def __init__(self, miner) -> None:
        self.processing_delay=0
        
        self.miner:Miner = miner
        self.miner_id = self.miner.miner_id
        self._network:Network = None
        self._receive_buffer:list[Packet]  = []
        self._forward_buffer:dict[str, list[Block]] = {OUTER:[],SELF:[]}

        self.withSegments = False
    
    
    def clear_forward_buffer(self):
        self._forward_buffer[OUTER].clear()
        self._forward_buffer[SELF].clear()
    
    def append_forward_buffer(self, msg:Message, type:str):
        """将要转发的消息添加到_forward_buffer中"""
        if type != SELF and type != OUTER:
            raise ValueError("Message type must be MINED or RECEIVED")
        if type == SELF:
            self._forward_buffer[SELF].append(msg)
        elif type == OUTER:
            self._forward_buffer[OUTER].append(msg)
    
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
    def get_reply(self, msg_name, target:int, err:str, round):
        ...
    @abstractmethod
    def remove_neighbor(self, remove_id:int):
        ...
    @abstractmethod
    def add_neighbor(self, add_id:int, round):
        ...
    @abstractmethod
    def getdata(self, inv:INVMsg):
        ...