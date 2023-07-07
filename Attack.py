import random
from chain import Block, Chain
from external import I
from miner import Miner
from functions import for_name
import global_var
import copy
import time
import network

def get_time(f):
    def inner(*arg,**kwarg):
        s_time = time.time()
        res = f(*arg,**kwarg)
        e_time = time.time()
        print('耗时：{}秒'.format(e_time - s_time))
        return res
    return inner

from abc import ABCMeta, abstractmethod
class Attack(metaclass=ABCMeta): 
    @abstractmethod
    def renew(self):
        # 更新adversary中的所有区块链状态：基准链 矿工状态(包括输入和其自身链 )
        pass

    @abstractmethod
    def clear(self):
        # clear the input tape and communcation tape
        pass

    @abstractmethod
    def adopt(self):
        # Adversary adopts the newest chain based on tthe adver's chains
        pass

    @abstractmethod
    def wait(self):
        # Adversary waits, and do nothing in current round.
        pass

    @abstractmethod
    def giveup(self):
        # Adversary gives up current attacking, like mining the blocks based on formal chain.
        pass

    @abstractmethod
    def match(self):
        # Although adversary did not attack successfuly, it broadcast the block at the same height of the main chain.
        pass

    @abstractmethod
    def mine(self):
        pass



    
class default_attack_mode(metaclass = ABCMeta):

    def __init__(self, q_ave, adversary_miner: list[Miner], global_chain: Chain, Environment_network: network):
        self.adversary: list[Miner] = adversary_miner # 使用list[Miner]为这个list及其元素定义类型
        self.current_miner = self.adversary[0] # 初始当前矿工代表
        self.q_ave = q_ave
        self.global_chain: Chain = global_chain
        self.Adverchain = copy.deepcopy(self.global_chain) # 攻击链 攻击者攻击手段挖出的块都暂时先加到这条链上
        self.base_chain = copy.deepcopy(self.global_chain) # 基准链 攻击者参考的链, 始终是以adversary视角出发的最新的链
        self.network: network = Environment_network
        self.adversary_miner_num = len(self.adversary) # 获取攻击者的数量
        self.q_adver = self.q_ave * self.adversary_miner_num # 计算攻击者全算力
        self.last_brd_block = None
        for temp_miner in self.adversary:
            # 重新设置adversary的 q 和 blockchian，原因在 mine_randmon_miner 部分详细解释了
            temp_miner.q = self.q_adver
            temp_miner.Blockchain.add_block_copy(self.Adverchain.lastblock)
        self.atlog={
            'chain_update': None,
            'input': None,
            'current_miner': None,
            'atk_mine': None,
            'override': None,
            'adopt': None,
            'receive_tape':[],
            'adminer_chain':[],
            'block_content': None,
            'base_chain': None,
            'adver_chain': None
        } # 对attack行为进行追踪记录的字典
        self.sttic={
            'over_ride': 0,
            'wait': 0,
            'give_up': 0
        } # 对attack行为进行统计的字典


    def renew(self, round): # 更新adversary中的所有区块链状态：基准链 矿工状态(包括输入和其自身链 )
        attack_update = False
        rcv_tape = []
        adminer_chain = []
        for temp_miner in self.adversary:
            rcv_tape.append([i.name for i in temp_miner.receive_tape])
            adminer_chain.append(temp_miner.Blockchain.lastblock.name)

            chain_update, update_index = temp_miner.maxvalid() # 模拟诚实矿工的BBP--验证区块 返回是否有更新

            self.atlog['adminer_chain'] = adminer_chain
            self.atlog['chain_update'] = chain_update.lastblock.name
            temp_miner.input = I(round, temp_miner.input_tape) # 模拟诚实矿工的BBP--输入
            self.atlog['input'] = temp_miner.input

            if chain_update.lastblock not in self.base_chain: # update_index 有很大问题只能用这个检测更新的链是否存在的方法
                # 这是一个非常严重的问题
                self.base_chain.add_block_copy(chain_update.lastblock) # 如果存在更新将更新的区块添加到基准链上 
                self.global_chain.add_block_copy(chain_update.lastblock) # 同时 也将该区块同步到全局链上
                attack_update = True
        # 此时base_chain应是以adversary视角中最优的基准链
        self.atlog['receive_tape'] = rcv_tape
        return attack_update
    
    def clear(self): # 清除矿工的input tape和communication tape
        for temp_miner in self.adversary:
            temp_miner.input_tape = []  # clear the input tape
            temp_miner.receive_tape = []  # clear the communication tape

    def mine(self):
        # 以下是attack模块攻击者挖矿部分的思路及原因
        '''
        miner 的 Mining 函数如下
        def Mining(self):
        return:
            self.Blockchain.lastblock 挖出的新区块没有就返回none type:Block/None
            mine_success 挖矿成功标识 type:Bool

        newblock, mine_success = self.consensus.mining_consensus(self.Blockchain,self.Miner_ID,self.isAdversary,self.input,self.q)
        if mine_success == True:
            self.Blockchain.AddBlock(newblock)
            self.Blockchain.lastblock = newblock
        return (newblock, mine_success)  # 返回挖出的区块，
        '''
        # 这里注意到如果调用 miner 自身的 mining 函数, 其使用的是 miner 自身的链以及 miner 自身的 q 
        # 因此为了能方便后续使用者便于书写attack模块, 在 attack 模块中的初始化部分替换 miner 的这两部分内容
        # 特别提醒： Miner_ID 和 isAdversary 部分是 Environment 初始化已经设置好的, input 在 renew 部分也处理完毕
        self.current_miner = random.choice(self.adversary) # 随机选取当前攻击者
        self.atlog['current_miner'] = self.current_miner.Miner_ID
        #newblock, mine_success = self.current_miner.Mining()
        self.current_miner.input = round
        adm_newblock, mine_success = self.current_miner.consensus.mining_consensus(\
            self.Adverchain,self.current_miner.Miner_ID,True,self.atlog['input'],self.current_miner.q)
        attack_mine = False
        if adm_newblock:
            self.atlog['block_content'] = adm_newblock.content
            attack_mine = True
            self.Adverchain.add_block_direct(adm_newblock)  # 自己挖出来的块直接用AddBlock即可
            self.Adverchain.lastblock = adm_newblock
            self.global_chain.add_block_copy(adm_newblock) # 作为历史可能分叉的一部添加到全局链中
            for temp_miner in self.adversary:
                temp_miner.receive_tape.append(adm_newblock)
                # 将新挖出的区块放在攻击者的receive_tape
        # return (newblock, mine_success)  # 返回挖出的区块，
        self.atlog['atk_mine'] = attack_mine
        '''
        
        if mine_success:
            attack_mine = True
            for temp_miner in self.adversary:
                #temp_miner.maxvalid() 
                # 虽然想直接使用maxvalid部分, 但是从逻辑上来说adversary之间利益是一致的, 他们可以直接通信所以应该直接addchain
                # 循环遍历了所有的adversary, 保证所有人都更新了区块
                #temp_miner.Blockchain.AddChain(newblock)
                # 另外特别提醒：AddChain部分本身使用了copy功能（且仅是对块的深拷贝）, 此外attack模块最好不要再使用copy功能
                self.global_chain.AddChain(newblock) # 作为历史可能分叉的一部添加到全局链中
                self.Adverchain.AddChain(newblock) # 攻击者挖出来的肯定要添加到Adverchain, 根据定义
                '''
        return attack_mine
    
    def mine_ID_miner(self, Miner_ID: int):
        # 所有功能与mine_randmon_miner一致 不赘述
        self.current_miner = self.adversary[Miner_ID] # 根据ID指定选取当前攻击者
        newblock, mine_success = self.current_miner.mining()
        attack_mine = False
        if mine_success:
            attack_mine = True
            for temp_miner in self.adversary:
                #temp_miner.maxvalid() 
                # 虽然想直接使用maxvalid部分 但是从逻辑上来说adversary之间利益是一致的 他们可以直接通信所以应该直接addchain
                # 循环遍历了所有的adversary 保证所有人都更新了区块
                temp_miner.Blockchain.add_block_copy(newblock)
                # 另外特别提醒：AddChain部分本身使用了copy功能（且仅是对块的深拷贝） 此外attack模块最好不要再使用copy功能
                self.global_chain.add_block_copy(newblock) # 作为历史可能分叉的一部添加到全局链中
                self.Adverchain.add_block_copy(newblock)
        return attack_mine
    
    def Override(self, round, cri = 1):
        # Override作为attack模块中最为直观的内容, 其功能是将adversary矿工挖到的区块发布出去
        # 但是这需要考虑adversary的行为策略：即何时将区块公布
        # 该基本实例中不考虑额外的行为模式, 只要执行了这个功能adversaery就将此时最新的区块接入网络中
        # 其中 cri 表示攻击链比环境主链高多少时执行接入网络
        # 即使是这种最基本的模式也能组合形成一些新的攻击策略
        # 前面也提到所有adversary挖出的区块都会被跟新到adverchain上所以要接入网络的就是该链
        attack_override = False
        if self.Adverchain.lastblock.BlockHeight() - self.base_chain.lastblock.BlockHeight() >= cri \
            and self.last_brd_block != self.Adverchain.lastblock:
            self.network.access_network(self.Adverchain.lastblock, self.current_miner.Miner_ID, round)
            attack_override = True
            self.last_brd_block = self.Adverchain.lastblock
        self.atlog['override'] = attack_override
        return attack_override
       
    def adopt(self):
        # 该功能是接纳环境中目前最新的链
        self.Adverchain.add_block_copy(self.base_chain.lastblock)
        # 首先将attack内的adverchain更新为attack可以接收到的最新的链
        for temp_miner in self.adversary:
            temp_miner.Blockchain.add_block_copy(self.base_chain.lastblock)
            # 更新所有攻击者的链
        

    def wait(self):
        # 这个功能就是什么都不干
        pass

    def giveup(self):
        # 放弃什么都不干
        pass

    def match(self, round):
        # match 的功能可以视为 Override 的一种, 但是又不完全相同
        # match 做到的行为本质上也是直接接入网络
        # 不论当前adverchain有多高, 即使比base_chain矮很多也发布
        self.network.access_network(self.Adverchain.lastblock, self.current_miner.Miner_ID, round)

    def attacklog2txt(self, round):
        RESULT_PATH = global_var.get_result_path()
        with open(RESULT_PATH / 'Attack_log.txt','a') as f:
            print('Round:',round,file=f)
            print('base chain:', self.base_chain.lastblock.BlockHeight(), self.base_chain.lastblock.name, file=f)
            print('Adverchain:', self.Adverchain.lastblock.BlockHeight(), self.Adverchain.lastblock.name, file=f)
            print(self.atlog, '\n',file=f)
    
    def resultlog2txt(self):
        RESULT_PATH = global_var.get_result_path()
        with open(RESULT_PATH / 'Attack_result.txt','a') as f:
            print(self.sttic, '\n',file=f)

    def excute_sample0(self, round):
        # 这是attack模块执行的攻击范例0: 算力攻击
        # 作为轮进行的chainxim, 每一轮执行时都要简介掌握当前局势, 输入round算是一个了解环境的维度

        # 每轮固定更新攻击状态
        
        attack_update = self.renew(round)
        # 执行挖掘
        attack_mine = self.mine()
        # 清空
        self.clear()
        # 执行override, 标准cri设定为高度2
        if attack_mine:
            self.network.access_network(self.Adverchain.lastblock, self.current_miner.Miner_ID, round)
            self.sttic['over_ride'] = self.sttic['over_ride']+1
        else:
            self.wait()
            self.sttic['wait'] = self.sttic['wait']+1
        
        self.adopt()



    def excute_sample1(self, round):
        # 这是attack模块执行的攻击范例1: 自私挖矿
        # 作为轮进行的chainxim, 每一轮执行时都要简介掌握当前局势, 输入round算是一个了解环境的维度

        # 每轮固定更新攻击状态
        
        attack_update = self.renew(round)
        # 执行挖掘
        attack_mine = self.mine()
        # 清空
        self.clear()
        # 执行override, 标准cri设定为高度2
        attack_override = self.Override(round, cri=2)
        
        if attack_override: # 如果成功执行了override, 就过
            self.atlog['adopt'] = False
            self.sttic['over_ride'] = self.sttic['over_ride']+1
        else:
            T1 = self.base_chain.lastblock.BlockHeight()
            T2 = self.Adverchain.lastblock.BlockHeight()
            self.atlog['base_chain'] = T1
            self.atlog['adver_chain'] = T2
            self.atlog['adopt'] = False
            if  T1-T2 >=2:
                # 如果没执行但是基准链比adverchaian高2, 则执行adopt, 认为attack在当前形式下无法超过基准链
                self.sttic['give_up'] = self.sttic['give_up']+1
                self.adopt()
                self.atlog['adopt'] = True
            else:
                self.wait() # 没成功执行override，也过
                self.sttic['wait'] = self.sttic['wait']+1

    def excute_sample2(self, round):
        # 这是attack模块执行的攻击返利2：双花攻击
        pass

    def excute_sample3(self, round):
        # 这是attack模块执行的攻击返利3：日蚀攻击
        pass





            
             

        


 
