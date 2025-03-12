from typing import TYPE_CHECKING

from data import Message

from .network_abc import Network, Packet

if TYPE_CHECKING:   
    from miner.miner import Miner


class PacketSyncNet(Packet):
    '''同步网络中的数据包，包含路由相关信息'''
    def __init__(self, payload, source_id: int):
        super().__init__(source_id, payload)    
class SynchronousNetwork(Network):
    """同步网络,在当前轮结束时将数据包传播给所有矿工"""

    def __init__(self, miners: list):
        super().__init__()
        self.withTopology = False
        self.withSegments = False
        
        self.miners:list[Miner] = miners
        for m in self.miners:
            m._join_network(self)

        # network_tape存储要广播的数据包和对应信息
        self.network_tape:list[PacketSyncNet] = []
        with open(self.NET_RESULT_PATH / 'network_log.txt', 'a') as f:
            print('Network Type: FullConnectedNetwork', file=f)

    def set_net_param(self):
        pass

    def access_network(self, new_msgs:list[Message], minerid:int, round:int,sendTogether:bool = False):
        """ 本轮新产生的消息添加到network_tape

        param
        -----
        new_msgs (list) : New incoming messages 
        minerid (int) : Miner_ID of the miner which generates the message. 
        round (int) : Current round. 
        """
        for msg in new_msgs:
            packet = PacketSyncNet(msg, minerid)
            self.network_tape.append(packet)

    def clear_NetworkTape(self):
        """清空network_tape"""
        self.network_tape = []

    def diffuse(self, round):
        """
        Diffuse algorism for `synchronous network`
        在本轮结束时，所有矿工都收到新消息

        param
        ----- 
        round (not use): The current round in the Envrionment.
        """
        for m in self.miners:
            m._NIC.nic_forward(round)
        if self.network_tape:
            for j in range(self.MINER_NUM):
                for packet in self.network_tape:
                    if j != packet.source:
                        self.miners[j]._NIC.nic_receive(packet)
            self.clear_NetworkTape()