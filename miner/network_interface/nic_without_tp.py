from copy import deepcopy
from data import Message
from network import Packet

from .._consts import FLOODING, OUTER_RCV_MSG, SELF_GEN_MSG
from .nic_abc import NetworkInterface


class NICWithoutTp(NetworkInterface):
    def __init__(self, miner) -> None:
        super().__init__(miner)

    def nic_join_network(self, network):
        """在环境初始化时加入网络"""
        self._network = network

    def nic_receive(self, packet: Packet):
        return self.miner.receive(packet.source, deepcopy(packet.payload))

    def nic_forward(self, round:int):
        if len(self._forward_buffer[SELF_GEN_MSG])==0:
            return 
        for msg,_,_ in self._forward_buffer[SELF_GEN_MSG]:
            self._network.access_network([msg], self.miner_id, round)
        self.clear_forward_buffer()
        
    
    def get_reply(self, msg_name, target:int, err:str, round):
        pass

    def remove_neighbor(self, remove_id:int):
        pass

    def add_neighbor(self, add_id:int, round):
        pass

    def reply_getdata(self):
        pass
