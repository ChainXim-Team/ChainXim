import time
from typing import List, Tuple

import global_var
from functions import BYTE_ORDER, INT_LEN, HASH_LEN, hash_bytes

from .consensus_abc import Consensus


class PoW(Consensus):

    class BlockHead(Consensus.BlockHead):
        '''适用于PoW共识协议的区块头'''
        __slots__ = ['target', 'nonce']
        def __init__(self, preblock: Consensus.Block = None, timestamp=0, content=0, miner_id=-1,
                     target = (2**(8*HASH_LEN) - 1).to_bytes(HASH_LEN, BYTE_ORDER),
                     nonce = 0):
            # currently content is an integer equal to the round the block is generated
            super().__init__(preblock, timestamp, content, miner_id)
            self.target = target  # 难度目标
            self.nonce = nonce  # 随机数

        def calculate_blockhash(self) -> bytes:
            data = self.miner.to_bytes(INT_LEN, BYTE_ORDER, signed=True)+ \
                    self.content.to_bytes(INT_LEN, BYTE_ORDER)+ \
                    self.prehash + \
                    self.nonce.to_bytes(INT_LEN, BYTE_ORDER)
            return hash_bytes(data).digest()

    def __init__(self,miner_id,consensus_params:dict):
        super().__init__(miner_id=miner_id)
        self.ctr=0 #计数器
        self.target = bytes.fromhex(consensus_params['target'])
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
        self.target = bytes.fromhex(consensus_params.get('target') or self.target)
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
        prehash = b_last.blockhash

        intermediate_hasher = hash_bytes(
            miner_id.to_bytes(INT_LEN, BYTE_ORDER, signed=True) + 
            x.to_bytes(INT_LEN, BYTE_ORDER) + prehash)
        
        i = 0
        while i < self.q:
            self.ctr = self.ctr+1
            hasher = intermediate_hasher.copy()
            hasher.update(self.ctr.to_bytes(INT_LEN, BYTE_ORDER))
            currenthash=hasher.digest()#计算哈希
            if currenthash<self.target:
                pow_success = True
                # blockhead = PoW.BlockHead(b_last,time.time_ns(),x,miner_id,self.target,self.ctr)
                # Use round instead as real world timestamp is meaningless in chainxim
                blockhead = PoW.BlockHead(b_last,round,x,miner_id,self.target,self.ctr)
                blocknew = PoW.Block(blockhead,b_last,isadversary,global_var.get_blocksize())
                self.ctr = 0
                return (blocknew, pow_success)
            else:
                i = i+1
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
        target = btemp.blockhead.target
        hash = btemp.calculate_blockhash()
        if hash >= target:
            return False
        else:
            return True
