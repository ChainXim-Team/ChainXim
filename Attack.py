import random
from consensus import Consensus
from chain import Block, Chain
from external import I
from miner import Miner
from functions import for_name
import global_var
import copy
import time
import network
import operator

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

    def __init__(self, adversary_miner: list[Miner], global_chain: Chain, Environment_network: network):
        self.adversary: list[Miner] = adversary_miner # 使用list[Miner]为这个list及其元素定义类型
        self.current_miner = self.adversary[0] # 初始当前矿工代表
        self.global_chain: Chain = global_chain
        self.Adverchain = copy.deepcopy(self.global_chain) # 攻击链 攻击者攻击手段挖出的块都暂时先加到这条链上
        self.base_chain = copy.deepcopy(self.global_chain) # 基准链 攻击者参考的链, 始终是以adversary视角出发的最新的链
        self.network: network.Network = Environment_network
        self.adversary_miner_num = len(self.adversary) # 获取攻击者的数量
        self.q_adver = sum([attacker.consensus.q for attacker in self.adversary]) # 计算攻击者总算力
        self.last_brd_block = None
        for temp_miner in self.adversary:
            # 重新设置adversary的 q 和 blockchain，原因在 mine_randmon_miner 部分详细解释了
            temp_miner.consensus.q = self.q_adver
            temp_miner.consensus.Blockchain.add_block_copy(self.base_chain.lastblock)
        adver_consensus_param = {'q_ave': self.q_adver, 'q_distr':'equal', 
                                 'target': temp_miner.consensus.target}
        self.Adverminer = AdverMiner(adver_consensus_param)
        self.Adverminer.consensus.Blockchain = self.Adverchain
        self.fork_blockhash = global_chain.lastblock.blockhash
        self.log={
            'round':0,
            'state_trans':None,
            'behaviour':None,
            'honest_block':None,
            'adver_block':None,
            'input': None
        }
        self.tmplog = copy.copy(self.log)

    def attack_record_chain(self):
        return self.local_record

    def renew(self, round): # 更新adversary中的所有区块链状态：基准链 矿工状态(包括输入和其自身链 )
        
        for temp_miner in self.adversary:
            chain_update, update_index = temp_miner.consensus.maxvalid() 
            self.log['input'] = I(round, temp_miner.input_tape) # 模拟诚实矿工的BBP--输入
            self.base_chain.add_block_copy(chain_update.lastblock) # 如果存在更新将更新的区块添加到基准链上 
            #self.local_record.add_block_copy(chain_update.lastblock) # 同时 也将该区块同步到全局链上
        newest_block = self.base_chain.lastblock
        return newest_block
    
    def clear(self): # 清除矿工的input tape和communication tape
        for temp_miner in self.adversary:
            temp_miner.input_tape = []  # clear the input tape
            temp_miner.consensus.receive_tape = []  # clear the communication tape

    def mine(self):
        # 以下是attack模块攻击者挖矿部分的思路及原因
        # 这里注意到如果调用 miner 自身的 mining 函数, 其使用的是 miner 自身的链以及 miner 自身的 q 
        # 因此为了能方便后续使用者便于书写attack模块, 在 attack 模块中的初始化部分替换 miner 的这两部分内容
        # 特别提醒： Miner_ID 和 isAdversary 部分是 Environment 初始化已经设置好的, input 在 renew 部分也处理完毕
        self.current_miner = random.choice(self.adversary) # 随机选取当前攻击者
        #self.atlog['current_miner'] = self.current_miner.Miner_ID
        adm_newblock, mine_success = self.Adverminer.consensus.mining_consensus(self.current_miner.Miner_ID,
                                                                                True,self.log['input'])
        attack_mine = False
        if adm_newblock:
            #self.atlog['block_content'] = adm_newblock.blockhead.content
            attack_mine = True
            self.Adverchain.add_block_direct(adm_newblock)  # 自己挖出来的块直接用AddBlock即可
            self.Adverchain.lastblock = adm_newblock
            self.global_chain.add_block_copy(adm_newblock) # 作为历史可能分叉的一部添加到全局链中
            for temp_miner in self.adversary:
                temp_miner.consensus.receive_tape.append(adm_newblock)
                # 将新挖出的区块放在攻击者的receive_tape
        return attack_mine
       
    def adopt(self):
        # 该功能是接纳环境中目前最新的链
        self.Adverchain.add_block_copy(self.base_chain.lastblock)
        # 首先将attack内的adverchain更新为attacker可以接收到的最新的链
        self.fork_blockhash = self.Adverchain.lastblock.blockhash
        return self.fork_blockhash
    
    def upload(self, round):
        self.network.access_network([self.Adverchain.lastblock], self.current_miner.Miner_ID, round)
        return self.Adverchain.lastblock
        
    def wait(self):
        # 这个功能就是什么都不干
        pass

    
    def resultlog2txt(self):
        RESULT_PATH = global_var.get_result_path()
        with open(RESULT_PATH / 'Attack_result.txt','a') as f:
            print(self.log, '\n',file=f)

    def execute_sample0(self, round):
        # 这是attack模块执行的攻击范例0: 算力攻击
        # 作为轮进行的chainxim, 每一轮执行时都要简介掌握当前局势, 输入round算是一个了解环境的维度
        # 每轮固定更新攻击状态      
        attack_update = self.renew(round)
        attack_mine = self.mine()# 挖矿 
        self.clear()# 清空
        self.adopt()
        # 执行override, 标准cri设定为高度2
        if attack_mine:
            self.upload(round)
        else:
            self.wait()

    def execute_sample1(self, round):
        # 这是attack模块执行的攻击范例1: 自私挖矿的beta版本，不同的实现思路
        # 作为轮进行的chainxim, 每一轮执行时都要简介掌握当前局势, 输入round算是一个了解环境的维度
        # 每轮固定更新攻击状态
        newest_block = self.renew(round)
        base_height = self.base_chain.lastblock.BlockHeight()
        adver_height = self.Adverchain.lastblock.BlockHeight()
        self.log['round']=round
        if base_height > adver_height:
            # 如果诚实链高于攻击链，进入0状态，全矿工认可唯一主链
            self.adopt()
            # 攻击者接受诚实链，诚实链为主链，诚实矿池获得收益，收益块数为从adverchain与base_chain产生分歧的块数开始。
            attack_mine = self.mine()
            if attack_mine:
                # 如果攻击者出块成功（在新主链上），从0状态进入1状态，攻击者处于领先1位置
                self.wait()
                #self.upload(round) #可能要upload
                self.log['state_trans']='1'
                self.log['behaviour']='wait'
                self.log['honest_block']=self.base_chain.lastblock.name,self.base_chain.lastblock.height
                self.log['adver_block']=self.Adverchain.lastblock.name,self.Adverchain.lastblock.height
                # 
            else:
                # 如果攻击者出块失败，在0状态停留，全矿工认可唯一主链
                self.wait()
                self.log['state_trans']='0'
                self.log['behaviour']='wait'
                self.log['honest_block']=self.base_chain.lastblock.name,self.base_chain.lastblock.height
                self.log['adver_block']=self.Adverchain.lastblock.name,self.Adverchain.lastblock.height
        else:
            # 当攻击链不低于基准链时，诚实矿工应该处于被攻击链主导状态或者与攻击链match状态。而攻击者能做的是尽可能挖矿，保持或占据主导地位，所以不存在接受链这一行为。
            # 故统计矿池收益的过程被设计在renew内完成。
            if base_height == adver_height:
                # 此时攻击链与诚实链等高
                if self.base_chain.lastblock.blockhash == self.Adverchain.lastblock.blockhash:
                    # 同高位置的区块相同，因此为0状态，攻击者尝试挖矿，挖出与否都不公布
                    attack_mine = self.mine()
                    # 如果挖出区块则进入1状态，否则停留在0状态
                    if attack_mine:
                        self.log['state_trans']='1'
                        self.log['behaviour']='mine selfly'
                        #self.upload(round) # chaixim适应性调整，挖出来必须要公布
                    else:
                        self.log['state_trans']='0'
                        self.log['behaviour']='wait'                   
                    self.log['honest_block']=self.base_chain.lastblock.name,self.base_chain.lastblock.height
                    self.log['adver_block']=self.Adverchain.lastblock.name,self.Adverchain.lastblock.height
                else:
                    # 同高位置的区块不相同，因此为0'状态，攻击者依然尝试挖矿
                    attack_mine = self.mine()
                    if attack_mine:
                        # 0'状态下攻击者若挖矿成功，以alpha概率进入0状态
                        block = self.upload(round)
                        self.log['state_trans']='0'
                        self.log['behaviour']='mine compete successfully, and upload'+ str(block.name)
                        self.log['honest_block']=self.base_chain.lastblock.name,self.base_chain.lastblock.height
                        self.log['adver_block']=self.Adverchain.lastblock.name,self.Adverchain.lastblock.height
                    else:
                        # 否则等待至下一回合，进入match状态。
                        '''
                        此时局面应是一部分诚实矿工本地连为攻击链，一部分为诚实链。攻击者本地全部为攻击链。
                        '''
                        block = self.upload(round) 
                        # 攻击者依然进行“区块主张”，尽可能让一些诚实矿工的本地链为攻击链，因此还是每回合upload区块。
                        self.wait()
                        # 但本质行为逻辑是wait
                        self.log['state_trans']='0#'
                        self.log['behaviour']='wait, and insist' + block.name
                        self.log['honest_block']=self.base_chain.lastblock.name,self.base_chain.lastblock.height
                        self.log['adver_block']=self.Adverchain.lastblock.name,self.Adverchain.lastblock.height
            else:
                # 这时，攻击链比诚实链高，高多少不知道。什么状态也不确定。
                if self.base_chain.lastblock.blockhash != self.fork_blockhash:
                    # 此时，攻击链和诚实链处于分叉了很久的状态。
                    if adver_height - base_height >=2:
                        # 如果攻击链比诚实链高大于等于2，则说明处于lead大于等于2的状态，只用挖矿就行
                        attack_mine = self.mine()
                        self.log['state_trans']=str(adver_height - base_height+1) if attack_mine else str(adver_height - base_height)
                        self.log['behaviour']=str(str(adver_height - base_height)+'→'+str(adver_height - base_height+1)\
                              if attack_mine else str(adver_height - base_height)+'→'+str(adver_height - base_height)) +', and wait'
                        self.log['honest_block']=self.base_chain.lastblock.name,self.base_chain.lastblock.height
                        self.log['adver_block']=self.Adverchain.lastblock.name,self.Adverchain.lastblock.height
                    else:
                        # 否则，攻击链仅比诚实链高1，受到威胁，攻击者必须立马公布当前区块，再挖矿，挖矿结果不影响
                        if self.log['state_trans'] !='1':
                            block = self.upload(round)
                            self.log['behaviour']='2→1, and upload' + block.name
                        attack_mine = self.mine()
                        self.log['behaviour']=str('1→2' if attack_mine else '1→1')
                        self.log['state_trans']='2' if attack_mine else '1'
                        
                        self.log['honest_block']=self.base_chain.lastblock.name,self.base_chain.lastblock.height
                        self.log['adver_block']=self.Adverchain.lastblock.name,self.Adverchain.lastblock.height
                else:
                    # 此时，攻击链从主链挖出若干隐形块，不需要担心受到威胁
                    attack_mine = self.mine()
                    self.wait()
                    self.log['state_trans']=str(adver_height - base_height+1) if attack_mine else str(adver_height - base_height)
                    self.log['behaviour']=str(str(adver_height - base_height)+'→'+str(adver_height - base_height+1)\
                          if attack_mine else str(adver_height - base_height)+'→'+str(adver_height - base_height))+', and wait'
                    self.log['honest_block']=self.base_chain.lastblock.name,self.base_chain.lastblock.height
                    self.log['adver_block']=self.Adverchain.lastblock.name,self.Adverchain.lastblock.height
        self.clear()
        #self.resultlog2txt()


        

    def execute_sample2(self, round):
        # 这是attack模块执行的攻击返利2：双花攻击
        pass

    def execute_sample3(self, round):
        # 这是attack模块执行的攻击返利3：日蚀攻击
        pass


class AdverMiner():
    '''代表整个攻击者集团的虚拟矿工对象，以Adverchain作为本地链，与全体攻击者共享共识参数'''
    ADVERMINER_ID = -1 # Miner_ID默认为ADVERMINER_ID
    def __init__(self, consensus_params):
        '''重写初始化函数，仅按需初始化Miner_ID、isAdversary以及共识对象'''
        self.Miner_ID = AdverMiner.ADVERMINER_ID #矿工ID
        self.isAdversary = True
        #共识相关
        self.consensus:Consensus = for_name(global_var.get_consensus_type())(AdverMiner.ADVERMINER_ID,
                                                                             consensus_params)

            
             

        


 
