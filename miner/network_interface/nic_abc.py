from abc import ABCMeta, abstractmethod

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


class NetworkInterface(metaclass=ABCMeta):
    def __init__(self, miner_id) -> None:
        self.processing_delay=0
        
        self.miner_id = miner_id
        self._network:Network = None
        self._receive_buffer:list[Packet]  = []
        self._forward_buffer:list = [] # 需要转发的消息
    
    def get_receive_msgs(self):
        return [p.payload for p in self._receive_buffer]

    @abstractmethod
    def receive_reply(self, msg):
        ...
    
    @abstractmethod
    def join_network(self, network):
        """在环境初始化时加入网络"""
        self._network = network

    @abstractmethod
    def nic_receive(self, packet: Packet):
        ...

    @abstractmethod
    def nic_forward(self, round:int):
        ...