from chain import Block, Chain
from consensus import Consensus
from functions import for_name
from external import I
# from external import validate
import global_var
##区块链不是链表，用树结构
##Q同步，认为有一个时延
##理论仿真器
##评估从文章里面3个指标
##互相怎么传参的

##标准程序，不管什么电脑环境运行出来的都是一致的

class Miner(object):

   
    def __init__(self, Miner_ID, q, target):
        self.Miner_ID = Miner_ID #矿工ID
        self.isAdversary = False
        self.q = q
        self.Blockchain = Chain(Miner_ID)   # 维护的区块链
        #共识相关
        self.consensus:Consensus = for_name(global_var.get_consensus_type())()    # 共识
        self.consensus.setparam(target)                                 # 设置共识参数
        #输入内容相关
        self.input = 0          # 要写入新区块的值
        self.input_tape = []
        #接收链相关
        self.receive_tape = []
        self.receive_history= [] #保留最近接收到的3个块
        self.buffer_size = 3
        #网络相关
        self.neighbor_list = []
        self.processing_delay=0    #处理时延
        
        #保存矿工信息
        CHAIN_DATA_PATH=global_var.get_chain_data_path()
        with open(CHAIN_DATA_PATH / f'chain_data{str(self.Miner_ID)}.txt','a') as f:
            print(f"Miner {self.Miner_ID}\n"
                f"is_adversary: {self.isAdversary}\n"
                f"q: {self.q}\n", file= f)

    

    def set_adversary(self, isAdversary:bool):
        '''
        设置是否为对手节点
        isAdversary=True为对手节点
        '''
        self.isAdversary = isAdversary


    def is_in_local_chain(self,block:Block):
        '''Check whether a block is in local chain,
        param: block: The block to be checked
        return: flagInLocalChain: Flag whether the block is in local chain.'''
        flagInLocalChain=False
        if block not in self.Blockchain:
            flagInLocalChain=False
        else:
            flagInLocalChain=True
        return flagInLocalChain


    def receive_block(self,rcvblock:Block):
        '''Interface between network and miner. 
        Append the rcvblock(have not received before) to receive_tape, 
        and add to local chain in the next round. 
        :param rcvblock: The block received from network. (Block)
        :return flagNotRcvBefore: If the rcvblock not in local chain or receive_tape, 
        return True.
        '''
        flagNotRcvBefore=False
        if rcvblock not in self.Blockchain and rcvblock not in self.receive_tape:
            self.receive_tape.append(rcvblock)
            # self.receive_history.append(rcvblock)
            # if len(self.receive_history)>=self.buffer_size:
                # del self.receive_history[0:len(self.receive_history)-self.buffer_size]
            flagNotRcvBefore=True
        else:
            flagNotRcvBefore = False
        return flagNotRcvBefore


    def mining(self):
        '''挖矿\n
        return:
            self.Blockchain.lastblock 挖出的新区块没有就返回none type:Block/None
            mine_success 挖矿成功标识 type:Bool
        '''
        newblock, mine_success = self.consensus.mining_consensus(self.Blockchain,self.Miner_ID,self.isAdversary,self.input,self.q)
        if mine_success is True:
            self.Blockchain.add_block_direct(newblock)
            self.Blockchain.lastblock = newblock
        return newblock, mine_success  # 返回挖出的区块，


    def maxvalid(self):
        # algorithm 2 比较自己的chain和收到的maxchain并找到最长的一条
        # output:
        #   lastblock 最长链的最新一个区块
        new_update = False  # 有没有更新
        if self.receive_tape==[]:
            return self.Blockchain, new_update
        for otherblock in self.receive_tape:
            copylist, insert_point = self.consensus.valid_partial(otherblock, self.Blockchain)
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
    
    
    def BackboneProtocol(self, round):
        chain_update, update_index = self.maxvalid()
        # if input contains READ:
        # write R(Cnew) to OUTPUT() 这个output不知干什么用的道
        self.input = I(round, self.input_tape)  # I function
        #print("outer2",honest_miner.input)
        newblock, mine_success = self.mining()
        #print("outer3",honest_miner.input)
        if update_index or mine_success:  # Cnew != C
            return newblock
        else:
            return None  #  如果没有更新 返回空告诉environment回合结束
        
    # def ValiChain(self, blockchain: Chain = None):
    #     '''
    #     检查是否满足共识机制\n
    #     相当于原文的validate
    #     输入:
    #         blockchain 要检验的区块链 type:Chain
    #         若无输入,则检验矿工自己的区块链
    #     输出:
    #         IsValid 检验成功标识 type:bool
    #     '''
    #     if blockchain is None:#如果没有指定链则检查自己
    #         IsValid=self.consensus.valid_chain(self.Blockchain.lastblock)
    #         if IsValid:
    #             print('Miner', self.Miner_ID, 'self_blockchain validated\n')
    #         else:
    #             print('Miner', self.Miner_ID, 'self_blockchain wrong\n')
    #     else:
    #         IsValid = self.consensus.valid_chain(blockchain)
    #         if not IsValid:
    #             print('blockchain wrong\n')
    #     return IsValid
