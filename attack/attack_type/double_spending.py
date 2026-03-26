'''
定义honestminging攻击
'''
import math
import random
from typing import Optional

import attack.attack_type as aa
import global_var
from data import Block
from collections import defaultdict
import copy


class DoubleSpending(aa.AttackType):
    '''
    算力攻击
    '''
    def __init__(self) -> None:
        super().__init__()
        self._log = {
            'honest_chain': None,
            'adver_chain': None,
            'success': 0,
            'fail':0,
            'behavior':None,
            'fork_block':None
        }
        self._simplifylog = {}
        self._fork_block: Block = None
        self._fork_height:int = 0
        self._attackblock = defaultdict(Block)
        self._lastattackblock: Block = None # 用于记录上传的最新的attackblock
        self._attack_success_detect: bool = False
        self.attackers_with_honest_neighbors:Optional[dict] = None # 记录每个攻击者的转发对象，记录至少有一个诚实邻居的攻击者列表
    
    def renew_stage(self, round):
        ## 1. renew stage
        if self.adver_list[0].network_has_topology:
            self.attackers_with_honest_neighbors = {}
            for attacker in self.adver_list:
                forwarding_targets = [neighbor_id for neighbor_id in attacker.neighbors if neighbor_id not in self.adver_list_ids]
                if len(forwarding_targets) > 0:
                    self.attackers_with_honest_neighbors[attacker] = forwarding_targets
        bh = self.behavior
        newest_block, mine_input = bh.renew(adver_list = self.adver_list,
                                 honest_chain = self.honest_chain,round = round,
                                 attackers_with_honest_neighbors=self.attackers_with_honest_neighbors)

        if self._attack_success_detect and (not self.adver_list[0].network_has_topology \
                                             or self.honest_chain.search_block(self._lastattackblock)):
            self._log['success'] = self._log['success'] + 1
            self._attack_success_detect = False
            self._fork_block = self._lastattackblock
            self._fork_height = self._fork_block.get_height()
        return newest_block, mine_input
    
    ATTACK_INITIAL_HEIGHT = 3 # 攻击开始的高度

    def attack_stage(self, round, mine_input):
        mine_input = self.behavior.ATTACKER_INPUT or mine_input
        bh = self.behavior
        n = self.attack_arg['N']
        ng = self.attack_arg['Ng']

        # 如果找到了合适的攻击者，随机选一个；
        if self.attackers_with_honest_neighbors:
            current_miners = list(self.attackers_with_honest_neighbors.keys()) # the initiators for the upload operation
            current_miner = random.choice(current_miners) # the miner that mines new blocks
        else:
            current_miners = random.sample(self.adver_list, 1)
            current_miner = current_miners[0]

        honest_height = self.honest_chain.last_block.get_height()
        if honest_height < self.ATTACK_INITIAL_HEIGHT:
            # 进行诚实挖矿，期间不计算攻击成功或者失败
            if self.honest_chain.get_height() > self.adver_chain.get_height():       
                self.behavior.adopt(adver_chain = self.adver_chain, honest_chain = self.honest_chain)
            attack_mine,block = self.behavior.mine(adver_list = self.adver_list,
                                            current_miner = current_miner,
                                            miner_input = mine_input,
                                            adver_chain = self.adver_chain,
                                            consensus = self.adver_consensus,
                                            round = round)
            if attack_mine:
                self.behavior.upload(adver_chain = self.adver_chain,
                                    current_miners = current_miners,
                                    round = round,
                                    adver_list = self.adver_list,
                                    fork_block = self.honest_chain.get_last_block(),
                                    syncLocalChain = False)
            return
        elif self._fork_block is None:
            self._fork_block = self.behavior.adopt(adver_chain = self.adver_chain, honest_chain = self.honest_chain)
            self._fork_height = self._fork_block.get_height()
        
        adver_height = self.adver_chain.last_block.get_height()

        if honest_height - self._fork_height < n:
            attack_mine,blocks = bh.mine(adver_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain, 
                                         consensus = self.adver_consensus,
                                         round = round)
            self._log['behavior'] = 'conforming ' + str(honest_height - self._fork_height+1) + '/' +str(n)
        elif honest_height - self._fork_height >= n:
            if honest_height - adver_height >= ng:
            # 攻击链比诚实链落后Ng个区块
                self._fork_block = bh.adopt(adver_chain = self.adver_chain, honest_chain = self.honest_chain)
                self._fork_height = self._fork_block.get_height()
                attack_mine,blocks = bh.mine(adver_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain,
                                         consensus = self.adver_consensus,
                                         round = round) 
                if self._log['behavior'] != 'adopt':
                    self._log['fail'] = self._log['fail'] + 1
                self._log['behavior'] = 'adopt'
                self._attack_success_detect = False
            elif adver_height >= honest_height:
                # 攻击链比诚实链长
                attack_mine,blocks = bh.mine(adver_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain, 
                                         consensus = self.adver_consensus,
                                         round = round)
                self._lastattackblock = self.adver_chain.get_last_block()
                blocks = bh.upload(adver_chain = self.adver_chain,
                        current_miners = current_miners, 
                        round = round,
                        adver_list = self.adver_list,
                        fork_block = self._fork_block, # if self._fork_block != None else self.honest_chain.head,
                        syncLocalChain = False)
                if self._log['behavior'] != 'override':
                    self._attack_success_detect = True

                self._log['behavior'] = 'override'
            # elif adver_height == honest_height - 1:
            #     attack_mine,blocks = bh.mine(adver_list = self.adver_list,
            #                              current_miner = current_miner,
            #                              miner_input = mine_input,
            #                              adver_chain = self.adver_chain,
            #                              consensus = self.adver_consensus,
            #                              round = round)
            #     if attack_mine:
            #         # 等长时，如果挖出来，则立刻发布
            #         blocks = bh.upload(adver_chain = self.adver_chain,
            #                      current_miners = current_miners, 
            #                      round = round,
            #                      adver_list = self.adver_list,
            #                      fork_block = self._fork_block if self._fork_block != None else self.honest_chain.head,
            #                      syncLocalChain = False)
            #         self._lastattackblock = self.adver_chain.get_last_block()
            #         if self._log['behavior'] != 'override':
            #             self._attack_success_detect = True
            #         self._log['behavior'] = 'override'
            #     else:
            #         self._log['behavior'] = 'matching'
            # else:
            #     # 攻击链与诚实链 matching
            #     attack_mine,blocks = bh.mine(adver_list = self.adver_list,
            #                              current_miner = current_miner,
            #                              miner_input = mine_input,
            #                              adver_chain = self.adver_chain, 
            #                              consensus = self.adver_consensus,
            #                              round = round)
            #     self._log['behavior'] = 'matching'
            else:
                # 攻击链与诚实链 matching
                attack_mine,blocks = bh.mine(adver_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain, 
                                         consensus = self.adver_consensus,
                                         round = round)
                cur_adver_height = self.adver_chain.get_height()
                if cur_adver_height >= honest_height:
                    latest_adver_chain_tip = self.adver_chain.get_last_block()
                    # 如果挖到了与诚实链等高或更高的块，则立刻发布与诚实链等高的块
                    send_chain_tip = self.adver_chain.get_last_block()
                    while send_chain_tip.get_height() > honest_height:
                        send_chain_tip = send_chain_tip.parentblock
                    self._lastattackblock = send_chain_tip
                    self.adver_chain.set_last_block(send_chain_tip) # 让攻击链回退到与诚实链等高的状态，以便上传
                    blocks = bh.upload(adver_chain = self.adver_chain,
                                 current_miners = current_miners, 
                                 round = round,
                                 adver_list = self.adver_list,
                                 fork_block = self._fork_block, # if self._fork_block != None else self.honest_chain.head,
                                 syncLocalChain = False)
                    self.adver_chain.set_last_block(latest_adver_chain_tip) # 恢复攻击链的状态
                    if self._log['behavior'] != 'override':
                        self._attack_success_detect = True
                    self._log['behavior'] = 'override'
                else:
                    self._log['behavior'] = 'matching'

    def clear_record_stage(self, round):
        bh = self.behavior
        self._log['honest_chain']=self.honest_chain.last_block.name,self.honest_chain.last_block.height
        self._log['adver_chain']=self.adver_chain.last_block.name,self.adver_chain.last_block.height
        self._log['fork_block']=(self._fork_block.name  if self._fork_block != None else self.honest_chain.head.name, 
                                 self._fork_block.height  if self._fork_block != None else 0)
        self._log['attacked_block'] = (self._lastattackblock.name if self._lastattackblock != None else None,
                                       self._lastattackblock.height if self._lastattackblock != None else 0)
        # self.__log['other']=self.__log['other']+' fork block is '+self.__fork_blockname
        bh.clear(adver_list = self.adver_list)# 清空
        self.resultlog2txt(round)
        
    def excute_this_attack_per_round(self, round):
        '''双花攻击'''
        ## 1. renew stage
        newest_block, mine_input= self.renew_stage(round)
        ## 2. attack stage
        self.attack_stage(round, mine_input)
        ## 3. clear and record stage
        self.clear_record_stage(round)

    def get_attack_times(self):
        return self._log['success']+self._log['fail']
    
    def info_getter(self,miner_num):
        rate, thr_rate = self.__success_rate(miner_num)
        return {'Success Rate': '{:.4f}'.format(self._log['success']/(self._log['success']+self._log['fail'])),
                'Theory rate in LockstepNetwork': '{:.4f}'.format(thr_rate),
                'Attack times': self._log['success']+self._log['fail'],
                # 'Success times': self._log['success'],
                'Ng': self.attack_arg['Ng'],
                'N': self.attack_arg['N'],
                'attack_fail': self._log['fail'],
                'attack_success': self._log['success']
                }
    
    def __success_rate(self,miner_num):
        if self._log['success'] != 0 or self._log['fail'] != 0:
            rate = self._log['success']/(self._log['success']+self._log['fail'])
            ## 计算理论成功率
            tmp = 0
            n = self.attack_arg['N']
            ng = self.attack_arg['Ng']
            beta = len(self.adver_list)/(miner_num-len(self.adver_list))
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
                        tmp = tmp + 1/(2**(n+j))*(math.factorial(j+n-1))/((math.factorial(j))*(math.factorial(n-1)))*((n-j+1)/(ng+1))
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
        
    def resultlog2txt(self,round):
        if self._simplifylog != self._log:
            self._simplifylog = copy.deepcopy(self._log)
            ATTACK_RESULT_PATH = global_var.get_attack_result_path()
            with open(ATTACK_RESULT_PATH / f'Attack Log.txt','a') as f:
                print(self._log,round, '\n',file=f)


