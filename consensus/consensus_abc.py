import random
from abc import ABCMeta, abstractmethod

import chain
import global_var
from chain import Chain

class Consensus(metaclass=ABCMeta):        #抽象类
    genesis_blockheadextra = {}
    genesis_blockextra = {}

    class BlockHead(chain.BlockHead):
        '''表述BlockHead的抽象类，重写初始化方法但是calculate_blockhash未实现'''
        def __init__(self, preblock:chain.Block=None, timestamp=0, content=0, miner_id=-1):
            '''此处的默认值为创世区块中的值'''
            prehash = preblock.calculate_blockhash() if preblock else 0
            super().__init__(prehash, timestamp, content, miner_id)

    class Block(chain.Block):
        '''与chain.Block功能相同但是重写初始化方法'''
        def __init__(self, blockhead: chain.BlockHead, preblock: chain.Block = None,
                     isadversary=False, blocksize_MB=2):
            '''当preblock没有指定时默认为创世区块，高度为0'''
            block_number = global_var.get_block_number() if preblock else 0
            height = preblock.height+1 if preblock else 0
            is_genesis = False if preblock else True
            super().__init__(f"B{block_number}", blockhead, height, isadversary, is_genesis, blocksize_MB)

    def create_genesis_block(self, chain:Chain, blockheadextra:dict = None, blockextra:dict = None):
        '''为指定链生成创世区块'''
        chain.head = self.Block(self.BlockHead())
        chain.lastblock = chain.head
        for k,v in blockheadextra or {}:
            setattr(chain.head.blockhead,k,v)
        for k,v in blockextra or {}:
            setattr(chain.head,k,v)

    def __init__(self,miner_id):
        self.Blockchain = Chain(miner_id)   # 维护的区块链
        self.create_genesis_block(self.Blockchain,self.genesis_blockheadextra,self.genesis_blockextra)
        self.receive_tape = [] #接收链相关

    def is_in_local_chain(self,block:chain.Block):
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
