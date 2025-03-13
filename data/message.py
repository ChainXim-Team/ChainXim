import math

import global_var


class Message(object):
    '''定义网络中传输的消息'''
    __slots__ = ['__name', 'size', 'segment_num'] 
    def __init__(self, name:str, size:float = 2):
        """
        Args:
            origin (int): 消息由谁产生的
            creation_round (int): 消息创建的时间
            size (float, optional): 消息的大小. Defaults to 2 MB.
        """
        self.segment_num = 1
        self.size = size
        self.__name = name
        if global_var.get_segmentsize() > 0 and self.size > 0:
            self.segment_num = math.ceil(self.size/global_var.get_segmentsize())
    
    @property
    def name(self):
        return self.__name
