'''
_atomization_behavior.py
给出攻击者原子化操作
'''

from abc import ABCMeta, abstractmethod


class AtomizationBehavior(metaclass=ABCMeta): 
    @abstractmethod
    def renew(self):
        # 更新adversary中的所有区块链状态：基准链 矿工状态(包括输入和其自身链 )
        pass

    @abstractmethod
    def clear(self):
        # clear the input tape and communcation tape
        pass

    @abstractmethod
    def adopt(self):
        # Adversary adopts the newest chain based on tthe adver's chains
        pass

    @abstractmethod
    def wait(self):
        # Adversary waits, and do nothing in current round.
        pass

    @abstractmethod
    def upload(self):
        # acceess to network
        pass

    @abstractmethod
    def mine(self):
        pass