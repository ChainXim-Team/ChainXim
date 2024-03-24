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
        b_last = self.local_chain.get_last_block()#链中最后一个块
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
        
    def maxvalid(self):
        # algorithm 2 比较自己的chain和收到的maxchain并找到最长的一条
        # output:
        #   lastblock 最长链的最新一个区块
        new_update = False  # 有没有更新
        if self._receive_tape==[]:
            return self.local_chain, new_update
        for otherblock in self._receive_tape:
            copylist, insert_point = self.valid_partial(otherblock)
            if copylist is not None:
                # 把合法链的公共部分加入到本地区块链中
                blocktmp = self.local_chain.add_blocks(blocks=copylist, insert_point=insert_point)  
                depthself = self.local_chain.get_height()
                depthOtherblock = otherblock.get_height()
                if depthself < depthOtherblock:
                    self.local_chain.set_last_block(blocktmp)
                    new_update = True
            else:
                print('error')  # 验证失败没必要脱出错误
        return self.local_chain, new_update

    def valid_partial(self, lastblock: Consensus.Block) -> Tuple[List[Consensus.Block], Consensus.Block]:
        '''验证某条链上不在本地链中的区块
        param:
            lastblock 要验证的链的最后一个区块 type:Block
        return:
            copylist 需要拷贝的区块list type:List[Block]
            insert_point 新链的插入点 type:Block
        '''
        receive_tmp = lastblock
        if not receive_tmp:  # 接受的链为空，直接返回
            return (None, None)
        copylist = []
        local_tmp = self.local_chain.search_block(receive_tmp)
        ss = receive_tmp.calculate_blockhash()
        while receive_tmp and not local_tmp:
            hash = receive_tmp.calculate_blockhash()
            block_vali = self.valid_block(receive_tmp)
            if block_vali and int(hash, 16) == int(ss, 16):
                ss = receive_tmp.blockhead.prehash
                copylist.append(receive_tmp)
                receive_tmp = receive_tmp.parentblock
                local_tmp = self.local_chain.search_block(receive_tmp)
            else:
                return (None, None)
        if receive_tmp:
            if int(receive_tmp.calculate_blockhash(), 16) == int(ss, 16):
                return (copylist, local_tmp)
            else:
                return (None, None)
        else:
            return (copylist, local_tmp)


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
        hash = btemp.blockhash
        if int(hash, 16) >= int(target, 16):
            return False
        else:
            return True
