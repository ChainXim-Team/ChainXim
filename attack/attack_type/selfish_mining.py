'''
定义honestminging攻击
'''
import random
import copy
import attack.attack_type as aa
import global_var
from data import Block, Chain


class SelfishMining(aa.AttackType):
    '''
    算力攻击
    '''
    def __init__(self) -> None:
        super().__init__()
        self._log = {
            'honest_chain': None,
            'adver_chain': None,
            'state': '0'
        }
        self._fork_block: Block = None
        self._simplifylog = {}

    def renew_stage(self, round):
        ## 1. renew stage
        bh = self.behavior
        newest_block, mine_input = bh.renew(adver_list = self.adver_list,
                                 honest_chain = self.honest_chain,round = round)
        return newest_block, mine_input

    def attack_stage(self, round, mine_input):
        ## 2. attack stage
        mine_input = self.behavior.ATTACKER_INPUT or mine_input
        bh = self.behavior
        honest_height = self.honest_chain.last_block.get_height()
        adver_height = self.adver_chain.last_block.get_height()
        current_miner = random.choice(self.adver_list)
        if honest_height > adver_height:
            # 如果诚实链高于攻击链，进入0状态，全矿工认可唯一主链
            self._fork_block = bh.adopt(adver_chain = self.adver_chain, 
                                         honest_chain = self.honest_chain)
            # 攻击者接受诚实链，诚实链为主链，诚实矿池获得收益，
            # 收益块数为从adver_chain与base_chain产生分歧的块数开始。
            attack_mine,block = bh.mine(adver_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain, 
                                         consensus = self.adver_consensus,
                                         round = round)
            if attack_mine:
                # 如果攻击者出块成功（在新主链上），从0状态进入1状态，攻击者处于领先1位置
                bh.wait()
                #self.upload(round) #可能要upload
                self._log['state']='1'
            else:
                # 如果攻击者出块失败，在0状态停留，全矿工认可唯一主链
                bh.wait()
                self._log['state']='0'
        else:
            # 当攻击链不低于基准链时，诚实矿工应该处于被攻击链主导状态或者与攻击链match状态。
            # 而攻击者能做的是尽可能挖矿，保持或占据主导地位，所以不存在接受链这一行为。
            # 故统计矿池收益的过程被设计在renew内完成。
            if honest_height == adver_height:
                # 此时攻击链与诚实链等高
                if self.honest_chain.last_block.blockhash == self.adver_chain.last_block.blockhash:
                    # 同高位置的区块相同，因此为0状态，攻击者尝试挖矿，挖出与否都不公布
                    attack_mine,block = bh.mine(adver_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain,
                                         consensus = self.adver_consensus,
                                         round = round)
                    # 如果挖出区块则进入1状态，否则停留在0状态
                    if attack_mine:
                        self._log['state']='1'
                        #self.upload(round) # chaixim适应性调整，挖出来必须要公布
                    else:
                        self._log['state']='0'
                else:
                    # 同高位置的区块不相同，因此为0'状态，攻击者依然尝试挖矿
                    attack_mine,block = bh.mine(adver_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain,
                                         consensus = self.adver_consensus,
                                         round = round)
                    if attack_mine:
                        # 0'状态下攻击者若挖矿成功，以alpha概率进入0状态
                        block = bh.upload(adver_chain = self.adver_chain,
                                 current_miner = current_miner, 
                                 round = round,
                                 adver_list = self.adver_list,
                                 fork_block= self._fork_block)
                        self._log['state']='0'
                    else:
                        # 否则等待至下一回合，进入match状态。
                        '''
                        此时局面应是一部分诚实矿工本地连为攻击链，一部分为诚实链。攻击者本地全部为攻击链。
                        '''
                        block = bh.upload(adver_chain = self.adver_chain,
                                 current_miner = current_miner, 
                                 round = round,
                                 adver_list = self.adver_list,
                                 fork_block= self._fork_block) 
                        # 攻击者依然进行“区块主张”，尽可能让一些诚实矿工的本地链为攻击链，因此还是每回合upload区块。
                        bh.wait()
                        # 但本质行为逻辑是wait
                        self._log['state']='0#'
            else:
                # 这时，攻击链比诚实链高，高多少不知道。什么状态也不确定。
                if self._fork_block == None:
                    self._fork_block = self.honest_chain.get_last_block()
                if self.honest_chain.last_block.blockhash != self._fork_block.blockhash: 
                    # 此时，攻击链和诚实链处于分叉了很久的状态。
                    if adver_height - honest_height >=2:
                        # 如果攻击链比诚实链高大于等于2，则说明处于lead大于等于2的状态，只用挖矿就行
                        attack_mine,block = bh.mine(adver_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain,
                                         consensus = self.adver_consensus,
                                         round = round)
                        self._log['state']=str(adver_height - honest_height+1) if attack_mine else str(adver_height - honest_height)
                    else:
                        # 否则，攻击链仅比诚实链高1，受到威胁，攻击者必须立马公布当前区块，再挖矿，挖矿结果不影响
                        if self._log['state'] !='1':
                            block = bh.upload(adver_chain = self.adver_chain,
                                 current_miner = current_miner, 
                                 round = round,
                                 adver_list = self.adver_list,
                                 fork_block= self._fork_block)
                        attack_mine,block = bh.mine(adver_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain, 
                                         consensus = self.adver_consensus,
                                         round = round)
                        self._log['state']='2' if attack_mine else '1'
                else:
                    # 此时，攻击链从主链挖出若干隐形块，不需要担心受到威胁
                    attack_mine,block = bh.mine(adver_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain,
                                         consensus = self.adver_consensus,
                                         round = round)
                    bh.wait()
                    self._log['state']=str(adver_height - honest_height+1) if attack_mine else str(adver_height - honest_height)        

    def clear_record_stage(self, round):
        # 3. clear and record stage
        bh = self.behavior
        bh.clear(adver_list = self.adver_list)# 清空
        self._log['honest_chain'] = self.honest_chain.last_block.name + ' Height:' + str(self.honest_chain.last_block.height)
        self._log['adver_chain'] = self.adver_chain.last_block.name + ' Height:' + str(self.adver_chain.last_block.height)
        self.resultlog2txt(round)
    
    def excute_this_attack_per_round(self, round):
        '''
        这是attack模块执行的攻击范例1: 自私挖矿的beta版本，不同的实现思路
        作为轮进行的chainxim, 每一轮执行时都要简介掌握当前局势, 输入round算是一个了解环境的维度
        每轮固定更新攻击状态
        '''
        ## 1. renew stage
        newest_block, mine_input = self.renew_stage(round)
        
        ## 2. attack stage
        self.attack_stage(round,mine_input)
        # 3. clear and record stage
        self.clear_record_stage(round)
        
    def info_getter(self,miner_num):
        return {'The proportion of adversary block in the main chain': 'See [Ratio of blocks contributed by malicious players]',
                'Theory region in SynchronousNetwork': self.__theory_propotion(miner_num)}
    

    def __theory_propotion(self,miner_num):
        def revenue(a,gama):
            R = (a*(1-a)**2*(4*a+gama*(1-2*a))-a**3)/(1-a*(1+(2-a)*a))
            return R
        thryRegion = ['%.4f'% revenue(len(self.adver_list)/miner_num,0), '%.4f'% revenue(len(self.adver_list)/miner_num,1)]

        return thryRegion

    def resultlog2txt(self,round):
        if self._simplifylog != self._log:
            self._simplifylog = copy.deepcopy(self._log)
            ATTACK_RESULT_PATH = global_var.get_attack_result_path()
            with open(ATTACK_RESULT_PATH / f'Attack Log.txt','a') as f:
                print(self._log,round, '\n',file=f)


