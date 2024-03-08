from abc import ABCMeta, abstractmethod

import global_var
from data import Block, Message

# packet type
DIRECT = "direct"
GLOBAL = "global"

# link errors
ERR_OUTAGE = "err_outage"


class Packet(object):
    def __init__(self, payload:Message):
        self.payload = payload
        
class INVMsg(Message):
    def __init__(self, source:int, target:int, block_to_forward:Block):
        """a simple `inv` message"""
        super().__init__(size=0)
        self.source = source
        self.target = target
        self.block:Block = block_to_forward

class GetDataMsg(Message):
    def __init__(self, source:int=None, target:int=None, 
                 block_name:str=None, require:bool=None):
        """a simple `getData` message"""
        super().__init__(size=0)
        self.source = source
        self.target:int = target
        self.block_name:str = block_name
        self.require:bool = require


class Network(metaclass=ABCMeta):
    """网络抽象基类"""

    def __init__(self) -> None:
        self.MINER_NUM = global_var.get_miner_num()  # 网络中的矿工总数，为常量
        self.NET_RESULT_PATH = global_var.get_net_result_path()

    @abstractmethod
    def set_net_param(self, *args, **kargs):
        pass

    @abstractmethod
    def access_network(self, new_msgs:list[Message], minerid:int, round:int):
        pass

    @abstractmethod
    def diffuse(self, round):
        pass