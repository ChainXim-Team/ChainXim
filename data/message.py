import math

import global_var


class Message(object):
    '''定义网络中传输的消息'''
    def __init__(self,  size:float = 2):# origin:int, creation_round:int,
        """
        Args:
            origin (int): 消息由谁产生的
            creation_round (int): 消息创建的时间
            size (float, optional): 消息的大小. Defaults to 2 MB.
        """
        # self.origin = origin
        # self.creation_round = creation_round
        self.size = size
        self.segment_num = 1
        if global_var.get_segmentsize() > 0 and self.size > 0:
            self.segment_num = math.ceil(self.size/global_var.get_segmentsize())