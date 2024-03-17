import time
from typing import List, Tuple

import global_var
from functions import hashG, hashH, hashsha256

from .consensus_abc import Consensus


class PoW(Consensus):

    class BlockHead(Consensus.BlockHead):
        '''适用于PoW共识协议的区块头'''
        def __init__(self, preblock: Consensus.Block = None, timestamp=0, content=0, miner_id=-1,
                     target = 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF',
                     nonce = 0):
            super().__init__(preblock, timestamp, content, miner_id)
            self.target = target  # 难度目标
            self.nonce = nonce  # 随机数

        def calculate_blockhash(self):
            return hashH([self.miner, self.nonce, hashG([self.prehash, self.content])])

    def __init__(self,miner_id,consensus_params:dict):
        super().__init__(miner_id=miner_id)
        self.ctr=0 #计数器
        self.target = consensus_params['target']
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
        self.target = consensus_params.get('target') or self.target
        self.q = consensus_params.get('q') or self.q

    def mining_consensus(self, miner_id, isadversary, x, round):
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
        if self.local_chain.is_empty():#如果区块链为空
            prehash = 0
        else:
            b_last = self.local_chain.last_block()#链中最后一个块
            prehash = b_last.blockhash
        currenthashtmp = hashsha256([prehash,x])    #要生成的块的哈希
        i = 0
        while i < self.q:
            self.ctr = self.ctr+1
            # if self._ctr>=10000000:#计数器最大值
            #     self._ctr=0
            currenthash=hashsha256([miner_id,self.ctr,currenthashtmp])#计算哈希
            if int(currenthash,16)<int(self.target,16):
                pow_success = True
                # blockhead = PoW.BlockHead(b_last,time.time_ns(),x,miner_id,self.target,self.ctr)
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
        pending_blocks:list[Consensus.Block] = [] # 待合并区块
        for incoming_block in self._receive_tape:
            if not isinstance(incoming_block, Consensus.Block):
                continue
            if self.valid_block(incoming_block):
                pending_blocks.append(incoming_block)
        pending_blocks.extend(self._block_buffer)
        self._block_buffer = []
        prev_death_height = self._block_buffer_death_height
        self._block_buffer_death_height = {}
        
        for incoming_block in pending_blocks:
            if insert_point := \
                self.local_chain.search_by_hash(incoming_block.blockhead.prehash, global_var.get_check_point()):
                blocktmp = self.local_chain.insert_block_copy([incoming_block], insert_point)
                depthself = self.local_chain.lastblock.get_height()
                depth_incoming_block = incoming_block.get_height()
                if depthself < depth_incoming_block:
                    self.local_chain.lastblock = blocktmp
                    new_update = True
            else:
                local_chain_height = self.local_chain.lastblock.get_height()
                death_height = prev_death_height.get(incoming_block.blockhash, local_chain_height+10)
                if local_chain_height >= death_height:
                    continue
                self._block_buffer.append(incoming_block)
                self._block_buffer_death_height[incoming_block.blockhash] = death_height

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
                if block_vali and int(hash, 16) == int(ss, 16):
                    ss = blocktmp.blockhead.prehash
                    blocktmp = blocktmp.last
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
        if int(hash, 16) >= int(target, 16):
            return False
        else:
            return True
