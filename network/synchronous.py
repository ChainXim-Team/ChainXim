from typing import TYPE_CHECKING
import random
from data import Message, Block
from .network_abc import Network, Packet

if TYPE_CHECKING:   
    from miner.miner import Miner


class PacketSyncNet(Packet):
    '''同步网络中的数据包，包含路由相关信息'''
    def __init__(self, payload, source_id: int):
        super().__init__(source_id, payload)    
class LockstepNetwork(Network):
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
        Diffuse algorism for `lockstep network`
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

class ZeroDelayNetwork(LockstepNetwork):
    """同步网络,在当前轮结束时将数据包传播给所有矿工"""

    def __init__(self, miners: list):
        super(LockstepNetwork, self).__init__()
        self.withTopology = False
        self.withSegments = False
        
        self.miners:list[Miner] = miners
        for m in self.miners:
            m._join_network(self)

        # network_tape存储要广播的数据包和对应信息
        self.network_tape:list[PacketSyncNet] = []
        self.pending_tape:list[PacketSyncNet] = []
        with open(self.NET_RESULT_PATH / 'network_log.txt', 'a') as f:
            print('Network Type: ZeroDelayNetwork', file=f)


    def diffuse(self, round):
        """
        Diffuse algorism for `lockstep network`
        在本轮结束时，所有矿工都收到新消息

        param
        ----- 
        round (not use): The current round in the Envrionment.
        """
        for m in self.miners:
            m._NIC.nic_forward(round)

        for block_packet in self.pending_tape:
            # 清空前一轮被延迟发送的区块
            self.propagate(block_packet)
        
        self.pending_tape = []
        max_height = 0
        level_set = []
        adversary_blocks:list[PacketSyncNet] = []
        if self.network_tape:
            for packet in self.network_tape:
                if isinstance(packet.payload, Block):
                    if packet.payload.isAdversaryBlock:
                        adversary_blocks.append(packet)
                        continue
                    if packet.payload.height > max_height:
                        max_height = packet.payload.height
                        self.pending_tape.extend(level_set)
                        level_set = [packet]
                    elif packet.payload.height == max_height:
                        level_set.append(packet)
                    else:
                        self.pending_tape.append(packet)
                else:
                    self.propagate(packet)
            self.clear_NetworkTape()

            for adversary_packet in adversary_blocks:
                if adversary_packet.payload.height == max_height:
                    level_set.append(adversary_packet)
                else:
                    self.propagate(adversary_packet)
            if self.pending_tape:
                # 随机选择一个区块进行传播，其他区块延迟到下一轮传播
                self.propagate(level_set.pop(random.randint(0, len(level_set)-1)))
            self.pending_tape.extend(level_set)

    def propagate(self, packet: PacketSyncNet):
        """同步网络在本轮结束时将数据包传播给所有矿工

        param
        -----
        round (int) : Current round. 
        """
        for j in range(self.MINER_NUM):
            if j != packet.source:
                self.miners[j]._NIC.nic_receive(packet)