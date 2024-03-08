'''
定义honestminging攻击
'''
import random

import attack.attack_type as aa
import global_var
from data import Block, Chain


class SelfishMining(aa.AttackType):
    '''
    算力攻击
    '''
    def __init__(self) -> None:
        super().__init__()
        self.__log = {
            'round': 0,
            'honest_chain': None,
            'adver_chain': None,
            'state': '0'
        }
        self.__fork_block: Block

    def renew_stage(self, round):
        ## 1. renew stage
        bh = self.behavior
        newest_block, mine_input = bh.renew(miner_list = self.adver_list,
                                 honest_chain = self.honest_chain,round = round)
        return newest_block, mine_input

    def attack_stage(self, round, mine_input):
        ## 2. attack stage
        bh = self.behavior
        honest_height = self.honest_chain.lastblock.get_height()
        adver_height = self.adver_chain.lastblock.get_height()
        current_miner = random.choice(self.adver_list)
        if honest_height > adver_height:
            # 如果诚实链高于攻击链，进入0状态，全矿工认可唯一主链
            self.__fork_block = bh.adopt(adver_chain = self.adver_chain, 
                                         honest_chain = self.honest_chain)
            # 攻击者接受诚实链，诚实链为主链，诚实矿池获得收益，
            # 收益块数为从adver_chain与base_chain产生分歧的块数开始。
            attack_mine = bh.mine(miner_list = self.adver_list, 
                                  current_miner = current_miner,
                                  miner_input = mine_input,
                                  adver_chain = self.adver_chain,
                                  global_chain = self.global_chain, 
                                  consensus = self.adver_consensus)
            if attack_mine:
                # 如果攻击者出块成功（在新主链上），从0状态进入1状态，攻击者处于领先1位置
                bh.wait()
                #self.upload(round) #可能要upload
                self.__log['state']='1'
            else:
                # 如果攻击者出块失败，在0状态停留，全矿工认可唯一主链
                bh.wait()
                self.__log['state']='0'
        else:
            # 当攻击链不低于基准链时，诚实矿工应该处于被攻击链主导状态或者与攻击链match状态。
            # 而攻击者能做的是尽可能挖矿，保持或占据主导地位，所以不存在接受链这一行为。
            # 故统计矿池收益的过程被设计在renew内完成。
            if honest_height == adver_height:
                # 此时攻击链与诚实链等高
                if self.honest_chain.lastblock.blockhash == self.adver_chain.lastblock.blockhash:
                    # 同高位置的区块相同，因此为0状态，攻击者尝试挖矿，挖出与否都不公布
                    attack_mine = bh.mine(miner_list = self.adver_list, current_miner = current_miner \
                              , miner_input = mine_input,\
                              adver_chain = self.adver_chain, \
                                global_chain = self.global_chain, consensus = self.adver_consensus)
                    # 如果挖出区块则进入1状态，否则停留在0状态
                    if attack_mine:
                        self.__log['state']='1'
                        #self.upload(round) # chaixim适应性调整，挖出来必须要公布
                    else:
                        self.__log['state']='0'
                else:
                    # 同高位置的区块不相同，因此为0'状态，攻击者依然尝试挖矿
                    attack_mine = bh.mine(miner_list = self.adver_list, current_miner = current_miner \
                              , miner_input = mine_input,\
                              adver_chain = self.adver_chain, \
                                global_chain = self.global_chain, consensus = self.adver_consensus)
                    if attack_mine:
                        # 0'状态下攻击者若挖矿成功，以alpha概率进入0状态
                        block = bh.upload(network = self.network, adver_chain = self.adver_chain, \
               current_miner = current_miner, round = round)
                        self.__log['state']='0'
                    else:
                        # 否则等待至下一回合，进入match状态。
                        '''
                        此时局面应是一部分诚实矿工本地连为攻击链，一部分为诚实链。攻击者本地全部为攻击链。
                        '''
                        block = bh.upload(network = self.network, adver_chain = self.adver_chain, \
               current_miner = current_miner, round = round) 
                        # 攻击者依然进行“区块主张”，尽可能让一些诚实矿工的本地链为攻击链，因此还是每回合upload区块。
                        bh.wait()
                        # 但本质行为逻辑是wait
                        self.__log['state']='0#'
            else:
                # 这时，攻击链比诚实链高，高多少不知道。什么状态也不确定。
                if self.honest_chain.lastblock.blockhash != self.__fork_block.blockhash:
                    # 此时，攻击链和诚实链处于分叉了很久的状态。
                    if adver_height - honest_height >=2:
                        # 如果攻击链比诚实链高大于等于2，则说明处于lead大于等于2的状态，只用挖矿就行
                        attack_mine = bh.mine(miner_list = self.adver_list, current_miner = current_miner \
                              , miner_input = mine_input,\
                              adver_chain = self.adver_chain, \
                                global_chain = self.global_chain, consensus = self.adver_consensus)
                        self.__log['state']=str(adver_height - honest_height+1) if attack_mine else str(adver_height - honest_height)
                    else:
                        # 否则，攻击链仅比诚实链高1，受到威胁，攻击者必须立马公布当前区块，再挖矿，挖矿结果不影响
                        if self.__log['state'] !='1':
                            block = bh.upload(network = self.network, adver_chain = self.adver_chain, \
               current_miner = current_miner, round = round)
                        attack_mine = bh.mine(miner_list = self.adver_list, current_miner = current_miner \
                              , miner_input = mine_input,\
                              adver_chain = self.adver_chain, \
                                global_chain = self.global_chain, consensus = self.adver_consensus)
                        self.__log['state']='2' if attack_mine else '1'
                else:
                    # 此时，攻击链从主链挖出若干隐形块，不需要担心受到威胁
                    attack_mine = bh.mine(miner_list = self.adver_list, current_miner = current_miner \
                              , miner_input = mine_input,\
                              adver_chain = self.adver_chain, \
                                global_chain = self.global_chain, consensus = self.adver_consensus)
                    bh.wait()
                    self.__log['state']=str(adver_height - honest_height+1) if attack_mine else str(adver_height - honest_height)        

    def clear_record_stage(self, round):
        # 3. clear and record stage
        bh = self.behavior
        bh.clear(miner_list = self.adver_list)# 清空
        self.__log['round']=round
        self.__log['honest_chain'] = self.honest_chain.lastblock.name + ' Height:' + str(self.honest_chain.lastblock.height)
        self.__log['adver_chain'] = self.adver_chain.lastblock.name + ' Height:' + str(self.adver_chain.lastblock.height)
        self.resultlog2txt()
    
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
        
    def info_getter(self):
        loop_block = self.global_chain.lastblock
        main_chain_height = loop_block.height
        adver_block_num = 0
        while(loop_block):
            if loop_block.isAdversaryBlock:
                adver_block_num += 1
            loop_block = loop_block.last
        return {'The proportion of adversary block in the main chain': '{:.4f}'.format(adver_block_num/ main_chain_height),
                'Theory region in SynchronousNetwork': self.__theory_propotion()}
    

    def __theory_propotion(self):
        def revenue(a,gama):
            R = (a*(1-a)**2*(4*a+gama*(1-2*a))-a**3)/(1-a*(1+(2-a)*a))
            return R
        thryRegion = ['%.4f'% revenue(len(self.adver_list)/len(self.miner_list),0), '%.4f'% revenue(len(self.adver_list)/len(self.miner_list),1)]

        return thryRegion

    def resultlog2txt(self):
        ATTACK_RESULT_PATH = global_var.get_attack_result_path()
        with open(ATTACK_RESULT_PATH / f'Attack Log.txt','a') as f:
            print(self.__log, '\n',file=f)


