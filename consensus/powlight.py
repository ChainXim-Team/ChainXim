import time
from typing import List, Tuple

import global_var
from functions import BYTE_ORDER, INT_LEN, HASH_LEN, hash_bytes

import random

from .consensus_abc import Consensus


class PoWlight(Consensus):

    class BlockHead(Consensus.BlockHead):
        '''适用于PoW共识协议的区块头'''
        __slots__ = ['target', 'nonce']
        def __init__(self, preblock: Consensus.Block = None, timestamp=0, content=0, miner_id=-1,
                     target = 0,
                     nonce = 0):
            # currently content is an integer equal to the round the block is generated
            super().__init__(preblock, timestamp, content, miner_id)
            self.target = target  # 难度目标
            self.nonce = nonce  # 随机数

        def calculate_blockhash(self) -> bytes:
            data = self.nonce
            return data

    def __init__(self,miner_id,consensus_params:dict):
        super().__init__(miner_id=miner_id)
        self.ctr=0 #计数器
        self.target = int(consensus_params['target'],16)    
        if consensus_params['q_distr'] == 'equal':
            self.q = consensus_params['q_ave']
        else:
            q_distr = eval(consensus_params['q_distr'])
            if isinstance(q_distr,list):
                self.q = q_distr[miner_id]
            else:
                raise ValueError("q_distr should be a list or the string 'equal'")

    def setparam(self,**consensus_params):
        '''
        设置pow参数,主要是target
        '''
        self.target = int(consensus_params.get('target') or self.target, 16)            
        self.q = consensus_params.get('q') or self.q

    def mining_consensus(self, miner_id:int, isadversary, x, round):
        '''计算PoW\n
        param:
            Miner_ID 该矿工的ID type:int
            x 写入区块的内容 type:any
            qmax 最大hash计算次数 type:int
        return:
            newblock 挖出的新块 type:None(未挖出)/Block
            pow_success POW成功标识 type:Bool
        '''
        pow_success = False
        #print("mine",Blockchain)
        b_last = self.local_chain.get_last_block()#链中最后一个块
        
        random_float = random.random()
        target_value = 1 - (1 - self.target/2**256)**self.q
        if random_float < target_value:
            pow_success = True
            self.ctr = random_float
            blockhead = PoWlight.BlockHead(b_last, round, x, miner_id, self.target, self.ctr)
            blocknew = PoWlight.Block(blockhead, b_last, isadversary, global_var.get_blocksize())
            return (blocknew, pow_success)
        return (None, pow_success)
        
    def local_state_update(self):
        # algorithm 2 比较自己的chain和收到的chain并相应更新本地链
        # output:
        #   lastblock 最长链的最新一个区块
        new_update = False  # 有没有更新
        #touched_hash_list = []
        for incoming_block in self._receive_tape:
            if not isinstance(incoming_block, Consensus.Block):
                continue
            if self.valid_block(incoming_block):
                prehash = incoming_block.blockhead.prehash
                if insert_point := self.local_chain.search_block_by_hash(prehash):
                    conj_block = self.local_chain.add_blocks(blocks=[incoming_block], insert_point=insert_point)
                    fork_tip, _ = self.synthesize_fork(conj_block)
                    #for block in touched_block:
                    #    touched_hash_list.append(block.blockhash)
                    depthself = self.local_chain.get_height()
                    depth_incoming_block = fork_tip.get_height()
                    if depthself < depth_incoming_block:
                        self.local_chain.set_last_block(fork_tip)
                        new_update = True
                else:
                    self._block_buffer.setdefault(prehash, [])
                    self._block_buffer[prehash].append(incoming_block)
        
        #self._block_buffer = {k: v for k, v in self._block_buffer.items() if k not in touched_hash_list}

        return self.local_chain, new_update

    def valid_chain(self, lastblock: Consensus.Block):
        '''验证区块链是否PoW合法\n
        param:
            lastblock 要验证的区块链的最后一个区块 type:Block
        return:
            chain_vali 合法标识 type:bool
        '''
        # xc = external.R(blockchain)
        # chain_vali = external.V(xc)
        chain_vali = True
        if chain_vali and lastblock:
            blocktmp = lastblock
            ss = blocktmp.calculate_blockhash()
            while chain_vali and blocktmp is not None:
                hash=blocktmp.calculate_blockhash()
                block_vali = self.valid_block(blocktmp)
                if block_vali and hash == ss:
                    ss = blocktmp.blockhead.prehash
                    blocktmp = blocktmp.parentblock
                else:
                    chain_vali = False
        return chain_vali

    def valid_block(self,block:Consensus.Block):
        '''
        验证单个区块是否PoW合法\n
        param:
            block 要验证的区块 type:Block
        return:
            block_vali 合法标识 type:bool
        '''
        btemp = block
        nonce = btemp.blockhead.calculate_blockhash()
        if nonce >= 1 - (1 - self.target/2**256)**self.q:
            return False
        else:
            return True