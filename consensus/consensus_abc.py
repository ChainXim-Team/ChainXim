import logging
import random
from abc import ABCMeta, abstractmethod

import data
import global_var

logger = logging.getLogger(__name__)

class Consensus(metaclass=ABCMeta):        #抽象类
    genesis_blockheadextra = {}
    genesis_blockextra = {}

    class BlockHead(data.BlockHead):
        '''表述BlockHead的抽象类，重写初始化方法但是calculate_blockhash未实现'''
        def __init__(self, preblock:data.Block=None, timestamp=0, content=0, miner_id=-1):
            '''此处的默认值为创世区块中的值'''
            prehash = preblock.blockhash if preblock else 0
            super().__init__(prehash, timestamp, content, miner_id)

    class Block(data.Block):
        '''与chain.Block功能相同但是重写初始化方法'''
        def __init__(self, blockhead: data.BlockHead, preblock: data.Block = None,
                     isadversary=False, blocksize_MB=2):
            '''当preblock没有指定时默认为创世区块，高度为0'''
            block_number = global_var.get_block_number() if preblock else 0
            height = preblock.height+1 if preblock else 0
            is_genesis = False if preblock else True
            super().__init__(f"B{block_number}", blockhead, height, 
                             isadversary, is_genesis, blocksize_MB)

    def create_genesis_block(self, chain:data.Chain, blockheadextra:dict = None, 
                             blockextra:dict = None):
        '''为指定链生成创世区块'''
        genesis_blockhead = self.BlockHead()
        for k,v in blockheadextra or {}:
            setattr(genesis_blockhead,k,v)
        chain.head = self.Block(genesis_blockhead)
        chain.lastblock = chain.head
        for k,v in blockextra or {}:
            setattr(chain.head,k,v)

    def __init__(self,miner_id):
        self.miner_id = miner_id
        self.local_chain = data.Chain(miner_id)   # 维护的区块链
        self.create_genesis_block(self.local_chain,self.genesis_blockheadextra,self.genesis_blockextra)
        self._receive_tape:list[data.Message] = [] # 接收到的消息
        self._forward_tape:list[data.Message] = [] # 需要转发的消息
        self._block_buffer:list[Consensus.Block] = [] # 区块缓存
        self._block_buffer_death_height:dict[str, int] = {} # Buffer中区块被丢弃的高度

    def is_in_local_chain(self,block:data.Block):
        '''Check whether a block is in local chain,
        param: block: The block to be checked
        return: Whether the block is in local chain.'''
        if self.local_chain.search(block, global_var.get_check_point()) is None:
            # logger.info("M%d %s not in local chain", self.miner_id, block.name)
            return False
        return True

    def receive_block(self,rcvblock:Block):
        '''Interface between network and miner. 
        Append the rcvblock(have not received before) to receive_tape, 
        and add to local chain in the next round. 
        :param rcvblock: The block received from network. (Block)
        :return: If the rcvblock not in local chain or receive_tape, return True.
        '''
        if rcvblock in self._receive_tape or rcvblock in self._block_buffer:
            return False
        if self.is_in_local_chain(rcvblock):
            return False
        self._receive_tape.append(rcvblock)
        random.shuffle(self._receive_tape)
        self._forward_tape.append(rcvblock)
        return True
            
    def receive_filter(self, msg: data.Message):
        '''接收事件处理，调用相应函数处理传入的对象'''
        if isinstance(msg, data.Block):
            return self.receive_block(msg)
        
    def get_forward_tape(self):
        return self._forward_tape

    def clear_forward_tape(self):
        self._forward_tape.clear()

    def consensus_process(self, isadversary, x, round):
        '''典型共识过程：挖出新区块并添加到本地链
        return:
            msg_list 包含挖出的新区块的列表，无新区块则为None type:list[Block]/None
            msg_available 如果有新的消息产生则为True type:Bool
        '''
        newblock, success = self.mining_consensus(self.miner_id , isadversary, x, round)
        if success is False:
            return None, False
        self.local_chain.add_block_direct(newblock)
        self.local_chain.lastblock = newblock
        self._forward_tape.append(newblock)
        logger.info("round %d, M%d mined %s", round, self.miner_id, newblock.name)
        return [newblock], True # 返回挖出的区块
            

    @abstractmethod
    def setparam(self,**consensus_params):
        '''设置共识所需参数'''
        pass

    @abstractmethod
    def mining_consensus(self, miner_id, isadversary, x):
        '''共识机制定义的挖矿算法
        return:
            新产生的区块  type:Block 
            挖矿成功标识    type:bool
        '''
        pass

    @abstractmethod
    def local_state_update(self):
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
