import time
from typing import List, Tuple
import global_var

from functions import hashsha256
from chain import BlockHead, Block, Chain
from .consensus_abc import Consensus


class PoW(Consensus):

    def __init__(self,miner_id):
        super().__init__(miner_id=miner_id)
        #self.target=global_var.get_PoW_target()
        # 严格来说target不应该出现在这里，因为这是跟共识有关的参数
        self.target = '0'
        self.q = 1
        self.ctr=0 #计数器

    def setparam(self,**consensus_params):
        '''
        设置pow参数,主要是target
        '''
        self.target = consensus_params['target']
        self.q = consensus_params['q']

    def mining_consensus(self,Miner_ID,isadversary,x):
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
        if self.Blockchain.is_empty():#如果区块链为空
            prehash = 0
            height = 0
        else:
            b_last = self.Blockchain.last_block()#链中最后一个块
            height = b_last.blockhead.height
            prehash = b_last.calculate_blockhash()
        currenthashtmp = hashsha256([prehash,x])    #要生成的块的哈希
        i = 0
        while i < self.q:
            self.ctr = self.ctr+1
            # if self._ctr>=10000000:#计数器最大值
            #     self._ctr=0
            currenthash=hashsha256([Miner_ID,self.ctr,currenthashtmp])#计算哈希
            if int(currenthash,16)<int(self.target,16):
                pow_success = True              
                blocknew=Block(''.join(['B',str(global_var.get_block_number())]),
                               BlockHead(prehash,currenthash,time.time_ns(),self.target,self.ctr,height+1,Miner_ID),
                               x,isadversary,False,global_var.get_blocksize())
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
        if self.receive_tape==[]:
            return self.Blockchain, new_update
        for otherblock in self.receive_tape:
            copylist, insert_point = self.valid_partial(otherblock)
            if copylist is not None:
                # 把合法链的公共部分加入到本地区块链中
                blocktmp = self.Blockchain.insert_block_copy(copylist, insert_point)  
                depthself = self.Blockchain.lastblock.BlockHeight()
                depthOtherblock = otherblock.BlockHeight()
                if depthself < depthOtherblock:
                    self.Blockchain.lastblock = blocktmp
                    new_update = True
            else:
                print('error')  # 验证失败没必要脱出错误
        return self.Blockchain, new_update

    def valid_partial(self, lastblock: Block) -> Tuple[List[Block], Block]:
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
        local_tmp = self.Blockchain.search(receive_tmp)
        ss = receive_tmp.calculate_blockhash()
        while receive_tmp and not local_tmp:
            block_vali = self.valid_block(receive_tmp)
            hash = receive_tmp.calculate_blockhash()
            if block_vali and int(hash, 16) == int(ss, 16):
                ss = receive_tmp.blockhead.prehash
                copylist.append(receive_tmp)
                receive_tmp = receive_tmp.last
                local_tmp = self.Blockchain.search(receive_tmp)
            else:
                return (None, None)
        if int(receive_tmp.calculate_blockhash(), 16) == int(ss, 16):
            return (copylist, local_tmp)
        else:
            return (None, None)

    def valid_chain(self, lastblock: Block):
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
                block_vali = self.valid_block(blocktmp)
                hash=blocktmp.calculate_blockhash()
                if block_vali and int(hash, 16) == int(ss, 16):
                    ss = blocktmp.blockhead.prehash
                    blocktmp = blocktmp.last
                else:
                    chain_vali = False
        return chain_vali

    def valid_block(self,block:Block):
        '''
        验证单个区块是否PoW合法\n
        param:
            block 要验证的区块 type:Block
        return:
            block_vali 合法标识 type:bool
        '''
        block_vali = False
        btemp = block
        target = btemp.blockhead.target
        hash = btemp.calculate_blockhash()
        if int(hash, 16) >= int(target, 16):
            return block_vali
        else:
            block_vali = True
            return block_vali
