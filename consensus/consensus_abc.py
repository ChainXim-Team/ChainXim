import random
from abc import ABCMeta, abstractmethod

from chain import Block, Chain
from functions import hashG, hashH

class Consensus(metaclass=ABCMeta):        #抽象类

    def __init__(self,miner_id):
        self.Blockchain = Chain(miner_id)   # 维护的区块链
        self.receive_tape = [] #接收链相关

    def is_in_local_chain(self,block:Block):
        '''Check whether a block is in local chain,
        param: block: The block to be checked
        return: Whether the block is in local chain.'''
        if self.Blockchain.search(block) is None:
            return False
        else:
            return True

    def receive_block(self,rcvblock:Block):
        '''Interface between network and miner. 
        Append the rcvblock(have not received before) to receive_tape, 
        and add to local chain in the next round. 
        :param rcvblock: The block received from network. (Block)
        :return: If the rcvblock not in local chain or receive_tape, return True.
        '''
        if not self.is_in_local_chain(rcvblock) and rcvblock not in self.receive_tape:
            self.receive_tape.append(rcvblock)
            random.shuffle(self.receive_tape)
            return True
        else:
            return False

    def consensus_process(self, Miner_ID, isadversary, x):
        '''典型共识过程：挖出新区块并添加到本地链
        return:
            self.Blockchain.lastblock 挖出的新区块没有就返回none type:Block/None
            mine_success 挖矿成功标识 type:Bool
        '''
        newblock, mine_success = self.mining_consensus(Miner_ID, isadversary, x)
        if mine_success is True:
            self.Blockchain.add_block_direct(newblock)
            self.Blockchain.lastblock = newblock
        return newblock, mine_success # 返回挖出的区块

    @abstractmethod
    def setparam(self,**consensus_params):
        '''设置共识所需参数'''
        pass

    @abstractmethod
    def mining_consensus(self, Miner_ID, isadversary, x):
        '''共识机制定义的挖矿算法
        return:
            新产生的区块  type:Block 
            挖矿成功标识    type:bool
        '''
        pass

    @abstractmethod
    def maxvalid(self):
        '''检验接收到的区块并将其合并到本地链'''
        pass

    @abstractmethod
    def valid_chain(self):
        '''检验链是否合法
        return:
            合法标识    type:bool
        '''
        pass

    @abstractmethod
    def valid_block(self):
        '''检验单个区块是否合法
        return:合法标识    type:bool
        '''
        pass
