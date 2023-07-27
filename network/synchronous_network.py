from chain import Block
from miner import Miner
from .network_abc import Network

class BlockPacketSyncNet(object):
    '''BoundedDelay网络中的区块数据包，包含路由相关信息'''
    def __init__(self, newblock: Block, minerid: int):
        self.block = newblock
        self.minerid = minerid
    
class SynchronousNetwork(Network):
    """同步网络,在当前轮结束时将区块传播给所有矿工"""

    def __init__(self, miners: list):
        super().__init__()
        self.miners:list[Miner] = miners
        # network_tape存储要广播的块和对应信息
        self.network_tape:list[BlockPacketSyncNet] = []
        with open(self.NET_RESULT_PATH / 'network_log.txt', 'a') as f:
            print('Network Type: FullConnectedNetwork', file=f)

    def set_net_param(self):
        pass

    def access_network(self, newblock, minerid, round):
        """ 本轮新产生的块添加到network_tape

        param
        -----
        newblock (Block) : The newly mined block 
        minerid (int) : Miner_ID of the miner generated the block. 
        round (int) : Current round. 
        """
        block_packet = BlockPacketSyncNet(newblock, minerid)
        self.network_tape.append(block_packet)

    def clear_NetworkTape(self):
        """清空network_tape"""
        self.network_tape = []

    def diffuse(self, round):
        """
        Diffuse algorism for `synchronous network`
        在本轮结束时，所有矿工都收到新块

        param
        ----- 
        round (not use): The current round in the Envrionment.
        """
        if self.network_tape:
            for j in range(self.MINER_NUM):
                for block_packet in self.network_tape:
                    if j != block_packet.minerid:
                        self.miners[j].receive_block(block_packet.block)
            self.clear_NetworkTape()