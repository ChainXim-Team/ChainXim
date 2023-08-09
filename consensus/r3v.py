import time
import math
from typing import List, Tuple
import pandas as pd

import global_var
from chain import BlockHead, Block, Chain
from functions import hashsha256, hashH
from .consensus_abc import Consensus


''' R3V共识 '''
class R3V(Consensus):

    def __init__(self,miner_id):
        super().__init__(miner_id)
        self.target = '0'
        #self.group = 99263413 # 最接近1亿的素数 
        self.group = int('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF43',16)
        # 115792089237316195423570985008687907853269984665640564039457584007913129639747
        # 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF43'
        # self.group = 33029
        self.primelist = pd.read_csv("prime_smaller10000000.csv").iloc

    def fastpower(self,a,n,b):
        # 快速幂取模算a^n%b
        ans = 1
        while n:
            if n&1:
                ans = ans*a%b
            a = a*a%b
            n >>= 1
        return ans%b

    def primeP(self,x:str,y:str,T):
        # 根据yx的hash计算小于2^T的质数作为证明参数
        prime_range = min(2**T,9288053) # 给定质数的上限
        prime_num = min(620421,round(prime_range/math.log(prime_range)))
        position = int(hashH([x,y]),16)%prime_num
        prime = self.primelist[position][1]
        if prime > 2**T:
            prime = 2
        return prime

    def setparam(self,**consensus_params):
        self.target = hex(int(consensus_params['target'],16)%self.group)[2:]
        self.q = consensus_params['q']

    def mining_consensus(self,Miner_ID,isadversary,x):
        '''计算VDF\n
        param:
            Miner_ID 该矿工的ID type:int
            x 写入区块的内容 type:any
        return:
            newblock 挖出的新块 type:None(未挖出)/Block
            VDF_success VDF成功标识 type:Bool
        '''
        VDF_success = False
        blocknew = None
        # s = 0
        # Blockchain.lastblock.blockhead.blockheadextra.setdefault("s",s)
        if self.Blockchain.lastblock.name == 'B0':
            s = 0            
            self.Blockchain.lastblock.blockhead.blockheadextra.setdefault("s",s)
            lastblock = self.Blockchain.last_block()
            height = lastblock.blockhead.height
            prehash = lastblock.calculate_blockhash()
        else:
            lastblock = self.Blockchain.last_block()
            s = lastblock.blockhead.blockheadextra["s"]
            height = lastblock.blockhead.height
            prehash = lastblock.calculate_blockhash()
        currenthashtmp = hashsha256([prehash,x])
        inputx = hex(int(hashH([Miner_ID,s]),16)%self.group)[2:]
        s = inputx
        # 这个s应该是作为全局共享的变量，每一轮会产生一个新的解s
        # 现在的处理方法是把s存在block里，这也符合逻辑
        # 在R3V原文中新输入s的生成使用了VRF，这里用minerID和s共同计算hash替代实现
        queryT = 1
        alpha = 1
        # 这里模拟动态难度，x是轮数，比较x和lastblock的高度
        # print("x",x)
        # print("height",lastblock.BlockHeight())
        '''
        alpha = alpha + (x - 1 - lastblock.BlockHeight())*0.2
        if int(lastblock.name[1:]) > 0.15*x:
            alpha = 1
            alpha = alpha - abs((int(lastblock.name[1:])-0.3*x))*0.5
        '''    
        while queryT <= self.q:
            m = int(s,16)**2%self.group
            # print("s:{}".format(m))
            # print("Target:{}".format(int(self.target,16)))
            s = hex(m)[2:]
            # print("  Query:{}".format(queryT),end="")
            
            F_s = int(hashH(s),16)%self.group
            # F_s = int(s,16)%self.group
            # print("  MinerID:{},F(s):{},Target:{}".format(Miner_ID,hex(F_s)[2:].zfill(64),hex(int(self.target,16))[2:].zfill(64)))
            
            if F_s <= round(int(self.target,16)*alpha):
                currenthash=hashsha256([Miner_ID,queryT,currenthashtmp])
                print("   Miner:{}".format(Miner_ID))
                print("   F_s:{}".format(F_s))
                print("   T:{}".format(queryT))
                print("   Target:{}".format(round(int(self.target,16)*alpha)))
                print("   Alpha:{}".format(alpha))
                VDF_success = True
                # 生成证明
                
                p = self.primeP(inputx,s,queryT)
                print("   p:{}".format(p))
                q = int(2**queryT//p)
                print("   q:{}".format(q))
                print("   x:{}".format(int(inputx,16)))
                proofPI = self.fastpower(int(inputx,16),q,self.group)
                print("   PI:{}".format(proofPI))

                blocknew=Block(''.join(['B',str(global_var.get_block_number())]),
                               BlockHead(prehash,currenthash,time.time_ns(),hex(round(int(self.target,16)*alpha)),queryT,height+1,Miner_ID),
                               x,isadversary)
                # R3V不使用块hash，故这里直接附None

                blocknew.blockhead.blockheadextra.setdefault("s",s)
                blocknew.blockhead.blockheadextra.setdefault("proofPI",proofPI)
                blocknew.blockhead.blockheadextra.setdefault("inputx",inputx)
                # 在块头的extra添加R3V需要用到的输入inputx、输出s和证明PI
                break

            queryT += 1
        return (blocknew,VDF_success)

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

    def valid_chain(self, lastblock:Block):
        '''检验链是否合法
        应return:
            合法标识    type:bool
        '''
        # R3V验证合法性其实和POW类似，验证当前块计算VDF的输入是否为上一个块的s与生成快的minerID共同hash
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
        '''
        验证单个区块是否R3V合法\n
        param:
            block 要验证的区块 type:Block
        return:
            block_vali 合法标识 type:bool
        '''
        
        # R3V 要验证两件事情：1. VDF计算结果是否正确，2. F(s)是否小于难度值
        block_vali = False
        if block.name == 'B0':
            return True
        x = block.blockhead.blockheadextra["inputx"]
        
        y = block.blockhead.blockheadextra["s"]
        pi = block.blockhead.blockheadextra["proofPI"]
        t = block.blockhead.nonce
        p = self.primeP(x,y,t)
        r = self.fastpower(2,t,p)
        x = int(x,16)
        y_0 = (self.fastpower(pi,p,self.group)*self.fastpower(x,r,self.group))%self.group
        F_s = int(hashH(y),16)%self.group

        if y_0 == int(y,16) and F_s <= int(block.blockhead.target,16):
            block_vali = True
        else:
            print(block.name)
            print("x",x)
            print("pi",pi)
            print("t",t)
            print("p",p)
            print("r",r)
            print("y_0",y_0)
            print("y",int(y,16))
            print(int(block.blockhead.target,16))

        return block_vali