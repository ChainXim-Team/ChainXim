from abc import ABCMeta, abstractmethod
from collections import defaultdict

import global_var
from data import Block, Message

# packet type
DIRECT = "direct"
GLOBAL = "global"

# link errors
ERR_OUTAGE = "err_outage"


class DataSegment(object):
    def __init__(self, origin_msg:Block, seg_id:int):
        self.origin_block = origin_msg
        self.seg_id = seg_id
    
    def __repr__(self) -> str:
        return str((self.origin_block.name, self.seg_id))

class Packet(object):
    def __init__(self, source:int, payload:Message|list[DataSegment]):
        self.source = source
        self.payload = payload
        
class INVMsg(Message):
    def __init__(self, source:int, target:int, block:Block,isFullChain:bool=False):
        super().__init__(size=0)
        self.source = source
        self.target = target
        self.block_or_seg:Block = block
        self.isFullChain = isFullChain

class GetDataMsg(Message):
    def __init__(self, source:int=None, target:int=None, 
                 req_blocks:list[Block]=None, require:bool=None):
        super().__init__(size=0)
        self.source = source
        self.target:int = target
        self.req_blocks:list[Block] = req_blocks
        self.req_segs:list = []
        self.isRequired:bool = require


class Network(metaclass=ABCMeta):
    """网络抽象基类"""

    def __init__(self) -> None:
        self.MINER_NUM = global_var.get_miner_num()  # 网络中的矿工总数，为常量
        self.NET_RESULT_PATH = global_var.get_net_result_path()
        self.withTopology = False
        self.withSegments = False
        self._dataitem_param = dict()

    @abstractmethod
    def set_net_param(self, *args, **kargs):
        pass

    @abstractmethod
    def access_network(self, new_msgs:list[Message], minerid:int, round:int, 
                       target:int = None, sendTogether:bool = False):
        pass

    @abstractmethod
    def diffuse(self, round):
        pass