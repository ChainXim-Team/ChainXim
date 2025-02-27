import math
import logging
from abc import ABCMeta, abstractmethod
from collections import defaultdict

import global_var
from data import Block, Message
from functions import INT_LEN

# packet type
DIRECT = "direct"
GLOBAL = "global"

# link errors
ERR_OUTAGE = "err_outage"

logger = logging.getLogger(__name__)

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
        
class INVMsg(object):
    def __init__(self, source:int, target:int, block:Block,isFullChain:bool=False):
        self.source = source
        self.target = target
        self.block_or_seg:Block = block
        self.isFullChain = isFullChain

class GetDataMsg(object):
    def __init__(self, source:int=None, target:int=None, 
                 req_blocks:list[Block]=None, require:bool=None):
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

    def message_preprocessing(self, msg:Message):
        if self._dataitem_param.get('dataitem_enable') and isinstance(msg, Block):
            msg.size = self._dataitem_param['dataitem_size'] * len(msg.blockhead.content) / 2 / INT_LEN
            if msg.size > self._dataitem_param['max_block_capacity'] * self._dataitem_param['dataitem_size']:
                logger.warning("The data items in block content exceeds the maximum capacity!")
                return False
            if global_var.get_segmentsize() > 0 and msg.size > 0:
                msg.segment_num = math.ceil(msg.size/global_var.get_segmentsize())
        return True

    @abstractmethod
    def set_net_param(self, *args, **kargs):
        pass

    @abstractmethod
    def access_network(self, new_msgs:list[Message|tuple[Message, int]], minerid:int, round:int, 
                       target:int = None, sendTogether:bool = False):
        pass

    @abstractmethod
    def diffuse(self, round):
        pass