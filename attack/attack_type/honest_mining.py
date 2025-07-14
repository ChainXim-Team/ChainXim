'''
定义honestminging攻击
'''
import random

import attack.attack_type as aa
import global_var
from data import Block, Chain
import copy

class HonestMining(aa.AttackType):
    '''
    算力攻击
    '''
    def __init__(self) -> None:
        super().__init__()
        self._log = {
            # 'round': 0,
            'honest_chain': None,
            'adver_chain': None,
            'fork_block': None
        }
        self._fork_block: Block = None
        self._simplifylog = {}
        self.attackers_with_honest_neighbors = None

    def renew_stage(self,round):
        ## 1. renew stage
        if self.adver_list[0].network_has_topology:
            self.attackers_with_honest_neighbors = []
            for attacker in self.adver_list:
                forwarding_targets = [neighbor_id for neighbor_id in attacker.neighbors if neighbor_id not in self.adver_list_ids]
                attacker.set_forwarding_targets(forwarding_targets)
                if len(forwarding_targets) > 0:
                    self.attackers_with_honest_neighbors.append(attacker)
        newest_block, mine_input = self.behavior.renew(adver_list = self.adver_list, 
                                    honest_chain = self.honest_chain,round = round,
                                    attackers_with_honest_neighbors=self.attackers_with_honest_neighbors)
        return newest_block, mine_input
    
    def attack_stage(self,round,mine_input):
        ## 2. attack stage
        # 如果找到了合适的攻击者，随机选一个；
        if self.attackers_with_honest_neighbors:
            current_miners = self.attackers_with_honest_neighbors
            current_miner = current_miners[0]
        else:
            current_miners = random.sample(self.adver_list, 1)
            current_miner = current_miners[0]

        if self.honest_chain.get_height() > self.adver_chain.get_height():       
            self._fork_block = self.behavior.adopt(adver_chain = self.adver_chain, honest_chain = self.honest_chain)
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
                                 fork_block = self._fork_block,
                                 syncLocalChain = False)
        else:
            self.behavior.wait()

    def clear_record_stage(self,round):
        ## 3. clear and record stage
        self.behavior.clear(adver_list = self.adver_list)# 清空
        # self._log['round'] = round
        self._log['honest_chain'] = self.honest_chain.last_block.name + ' Height:' + str(self.honest_chain.last_block.height)
        self._log['adver_chain'] = self.adver_chain.last_block.name + ' Height:' + str(self.adver_chain.last_block.height)
        self.resultlog2txt(round)


    def excute_this_attack_per_round(self, round):
        
        ## 1. renew stage
        newest_block, mine_input = self.renew_stage(round)
        ## 2. attack stage
        self.attack_stage(round, mine_input)
        ## 3. clear and record stage
        self.clear_record_stage(round)
        
        
    def info_getter(self, miner_num):
        

        return None
    

    def resultlog2txt(self,round):
        if self._simplifylog != self._log:
            self._simplifylog = copy.deepcopy(self._log)
            ATTACK_RESULT_PATH = global_var.get_attack_result_path()
            with open(ATTACK_RESULT_PATH / f'Attack Log.txt','a') as f:
                print(self._log,round, '\n',file=f)


