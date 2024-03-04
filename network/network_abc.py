from abc import ABCMeta, abstractmethod

import global_var
from data import Message


class Packet(object):
    def __init__(self, payload:Message):
        self.payload = payload
        

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