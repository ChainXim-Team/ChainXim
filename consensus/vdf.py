import math
import time
from typing import List, Tuple
import pandas as pd

import global_var
from chain import BlockHead, Block, Chain
from functions import hashsha256, hashH
from .consensus_abc import Consensus

class VDF(Consensus):
    def __init__(self,miner_id):
        super().__init__(miner_id)
        self.target = '0' # 最接近1亿的素数
        self.group = int('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF43',16)
        self.primelist = pd.read_csv("prime_smaller10000000.csv").iloc
        self.startmining = True
        self.isblocknew = True
        self.start_mine_time = 0
        self.para = {
            'T':0,
            'x':0,
            'y':0,
            'p':0,
            'q':0,
            'pi':0
        }
        self.ctr = 0
        self.blockmining_prehash = ''


    def setparam(self,**consensus_params):
        '''设置共识所需参数'''
        self.qmax = consensus_params['q']
        self.start = 50*self.qmax
        self.gap = 500*self.qmax

    def primeP(self,x:str,y:str,T):
        # 根据yx的hash计算小于2^T的质数作为证明参数
        prime_range = min(2**T,9288053) # 给定质数的上限
        prime_num = min(620421,round(prime_range/math.log(prime_range)))
        position = int(hashH([x,y]),16)%prime_num
        prime = self.primelist[position][1]
        if prime > 2**T:
            prime = 2
        return prime

    def fastpower(self,a,n,b):
        # 快速幂取模算a^n%b
        n = int(n)
        ans = 1
        while n:
            if (n)&1:
                ans = ans*a%b
            a = a*a%b
            n >>= 1
        return ans%b

    def mining_consensus(self,Miner_ID,isadversary,x):
        '''共识机制定义的挖矿算法
        应return:
            新产生的区块  type:Block 
            挖矿成功标识    type:bool
        '''
        bctemp = self.Blockchain
        b_last = bctemp.last_block()#链中最后一个块
        height = b_last.height
        prehashtmp = b_last.calculate_blockhash()
        # 每轮mine q次前都要看看现在最新的块是不是自己正在挖的
        if prehashtmp != self.blockmining_prehash:
            self.blockmining_prehash = prehashtmp
            self.isblocknew = True
        
        
        if self.startmining or self.isblocknew:
            self.start_mine_time = time.time()
            self.startmining = False
            self.isblocknew = False
            # 初始化
            self.para['T'] = int(hashsha256([Miner_ID,self.start_mine_time,x]),16) % self.gap + self.start
            self.para['x'] = int(hashsha256([Miner_ID,self.blockmining_prehash]),16) % self.group
            self.para['y'] = self.fastpower(self.para['x'],2**self.para['T'],self.group)
            self.para['p'] = self.primeP(self.para['x'], self.para['y'], self.para['T'])
            self.para['q'] = 2**self.para['T']//self.para['p']
            self.para['pi'] = self.fastpower(self.para['x'],self.para['q'],self.group)
            self.ctr = self.para['T']
        
        if self.ctr - self.qmax < self.qmax:
            currenthashtmp = hashsha256([self.blockmining_prehash,x])    #要生成的块的哈希
            currenthash=hashsha256([Miner_ID,self.para['T'],currenthashtmp])
            blocknew=Block(''.join(['B',str(global_var.get_block_number())]),
                                BlockHead(self.blockmining_prehash,currenthash,time.time_ns(),hex(round(int(self.target,16))),self.para['T'],height+1,Miner_ID),
                                x,isadversary)
            blocknew.blockhead.blockheadextra.setdefault("start_mine_time",self.start_mine_time)
            blocknew.blockhead.blockheadextra.setdefault("pi_i",self.para['pi'])
            blocknew.blockhead.blockheadextra.setdefault("y_i",self.para['y'])
            blocknew.blockhead.blockheadextra.setdefault("qmax",self.qmax)
            # blocknew.blockhead.blockheadextra.setdefault("T",self.para['T'])
            # blocknew.blockhead.blockheadextra.setdefault("ex",[Miner_ID,self.start_mine_time,x])
            return (blocknew, True)
        else:
            self.ctr -= self.qmax
            return (None, False)

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
            local_chain 本地区块链 tyep:Chain
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


    def valid_chain(self,lastblock:Block):
        '''检验链是否合法
        应return:
            合法标识    type:bool
        '''
        chain_vali = True
        if lastblock.BlockHeight() != 0:
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
        '''检验单个区块是否合法
        应return:合法标识    type:bool
        '''
        block_vali = True
        if block.name == 'B0':
            block_vali = True
            return block_vali
        
        Miner = block.blockhead.miner
        
        content = block.blockhead.content
        prehash = block.blockhead.prehash
        y_i = block.blockhead.blockheadextra['y_i']
        pi_i = block.blockhead.blockheadextra['pi_i']
        start_mine_time = block.blockhead.blockheadextra['start_mine_time']
        qmax = block.blockhead.blockheadextra['qmax']
        T_i = int(hashsha256([Miner,start_mine_time,content]),16) % self.gap + self.start
        t_0 = block.blockhead.nonce
        # print(T_i,t_0)
        x_i = int(hashsha256([Miner,prehash]),16) % self.group
        p_i = self.primeP(x_i, y_i, T_i)
        r = self.fastpower(2, T_i, p_i)
        y_0 = (self.fastpower(pi_i,p_i,self.group)*self.fastpower(x_i,r,self.group)) % self.group

        if y_0 == y_i:
            block_vali = True
        return block_vali