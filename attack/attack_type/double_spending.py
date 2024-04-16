'''
定义honestminging攻击
'''
import math
import random

import attack.attack_type as aa
import global_var
from data import Block


class DoubleSpending(aa.AttackType):
    '''
    算力攻击
    '''
    def __init__(self) -> None:
        super().__init__()
        self._log = {
            'round': 0,
            'honest_chain': None,
            'adver_chain': None,
            'success': 0,
            'fail':0,
            'behavior':None,
            'fork_block':None
        }
        self._fork_block: Block = None
        self._fork_height:int = 0
        self._fork_blockname = None
    
    def renew_stage(self, round):
        ## 1. renew stage
        bh = self.behavior
        newest_block, mine_input = bh.renew(miner_list = self.adver_list,
                                 honest_chain = self.honest_chain,round = round)
        return newest_block, mine_input

    def attack_stage(self, round, mine_input):
        bh = self.behavior
        n = self.attack_arg['N']
        ng = self.attack_arg['Ng']
        honest_height = self.honest_chain.last_block.get_height()
        adver_height = self.adver_chain.last_block.get_height()
        current_miner = random.choice(self.adver_list)
        if honest_height - self._fork_height < n:
            attack_mine = bh.mine(miner_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain,
                                         global_chain = self.global_chain, 
                                         consensus = self.adver_consensus,
                                         round = round)
            self._log['behavior'] = 'conforming ' + str(honest_height - self._fork_height) + '/' +str(n)
        elif honest_height - self._fork_height >= n:
            if honest_height - adver_height >= ng:
            # 攻击链比诚实链落后Ng个区块
                self._fork_block = bh.adopt(adver_chain = self.adver_chain, honest_chain = self.honest_chain)
                self._fork_blockname = self._fork_block.name
                self._fork_height = self._fork_block.get_height()
                attack_mine = bh.mine(miner_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain,
                                         global_chain = self.global_chain, 
                                         consensus = self.adver_consensus,
                                         round = round) 
                if self._log['behavior'] != 'adopt':
                    self._log['fail'] = self._log['fail'] + 1
                self._log['behavior'] = 'adopt'
            elif adver_height > honest_height:
                block = bh.upload(network = self.network, 
                                 adver_chain = self.adver_chain,
                                 current_miner = current_miner, 
                                 round = round,
                                 miner_list = self.adver_list,
                                 fork_block= self._fork_block)
                attack_mine = bh.mine(miner_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain,
                                         global_chain = self.global_chain, 
                                         consensus = self.adver_consensus,
                                         round = round)
                if attack_mine:
                    block = bh.upload(network = self.network, 
                                 adver_chain = self.adver_chain,
                                 current_miner = current_miner, 
                                 round = round,
                                 miner_list = self.adver_list,
                                 fork_block= self._fork_block)
                if self._log['behavior'] != 'override':
                    self._log['success'] = self._log['success'] + 1
                self._log['behavior'] = 'override'
            else:
                attack_mine = bh.mine(miner_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain,
                                         global_chain = self.global_chain, 
                                         consensus = self.adver_consensus,
                                         round = round)
                self._log['behavior'] = 'matching'

    def clear_record_stage(self, round):
        bh = self.behavior
        self._log['honest_chain']=self.honest_chain.last_block.name,self.honest_chain.last_block.height
        self._log['adver_chain']=self.adver_chain.last_block.name,self.adver_chain.last_block.height
        self._log['fork_block']=self._fork_blockname
        # self.__log['other']=self.__log['other']+' fork block is '+self.__fork_blockname
        bh.clear(miner_list = self.adver_list)# 清空
        self.resultlog2txt()
        
    def excute_this_attack_per_round(self, round):
        '''双花攻击'''
        ## 1. renew stage
        newest_block, mine_input = self.renew_stage(round)
        ## 2. attack stage
        self.attack_stage(round, mine_input)
        ## 3. clear and record stage
        self.clear_record_stage(round)

        
    def info_getter(self):

        rate, thr_rate = self.__success_rate()
        return {'Success Rate': '{:.4f}'.format(rate),
                'Theory rate in SynchronousNetwork': '{:.4f}'.format(thr_rate),
                'Attack times': self._log['success']+self._log['fail'],
                'Success times': self._log['success'],
                'Ng': self.attack_arg['Ng'],
                'N': self.attack_arg['N']
                }
    
    def __success_rate(self):
        if self._log['success'] != 0 or self._log['fail'] != 0:
            rate = self._log['success']/(self._log['success']+self._log['fail'])
            ## 计算理论成功率
            tmp = 0
            n = self.attack_arg['N']
            ng = self.attack_arg['Ng']
            beta = len(self.adver_list)/(len(self.miner_list)-len(self.adver_list))
            if ng > 100*n:
                # Ng 非常大
                if beta >= 1:
                    thr_rate = 1
                else:
                    for j in range(0, n+1):
                        tmp = tmp + (math.factorial(j+n-1))/((math.factorial(j))*(math.factorial(n-1)))\
                        *((1/(1+beta))**n)*((beta/(1+beta))**j)*(1-beta**(n-j+1))
                    thr_rate = 1-tmp
            else:
                # Ng 正常
                if beta == 1:
                    for j in range(0, n+1):
                        1/(2**(n+j))*(math.factorial(j+n-1))/((math.factorial(j))*(math.factorial(n-1)))*((n-j+1)/(ng+1))
                    thr_rate = 1-tmp
                else:
                    for j in range(0, n+1):
                        tmp = tmp + (math.factorial(j+n-1))/((math.factorial(j))*(math.factorial(n-1)))\
                        *((1/(1+beta))**n)*((beta/(1+beta))**j)*((1-beta**(n-j+1))/(1-beta**(ng+1)))
                    thr_rate = 1-tmp
            ##
            return rate, thr_rate
        else:
            return -1,-1
        
    def resultlog2txt(self):
        ATTACK_RESULT_PATH = global_var.get_attack_result_path()
        with open(ATTACK_RESULT_PATH / f'Attack Log.txt','a') as f:
            print(self._log, '\n',file=f)


