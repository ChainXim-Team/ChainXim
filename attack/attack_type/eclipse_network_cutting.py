'''
定义honestminging攻击
'''
import random

import attack.attack_type as aa
import global_var
from data import Block, Chain
import copy

class EclipseNetworkCutting(aa.AttackType):
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

    def renew_stage(self,round):
        ## 1. renew stage
        newest_block, mine_input,incoming_block_from_eclipse = self.behavior.renew(adver_list = self.adver_list, 
                                    honest_chain = self.honest_chain,round = round,
                                    eclipse_list_ids = self.eclipsed_list_ids)
        return newest_block, mine_input
    
    def attack_stage(self,round,mine_input):
        ## 2. attack stage
        current_miner = random.choice(self.adver_list)
        if self.honest_chain.get_height() > self.adver_chain.get_height():       
            self._fork_block = self.behavior.adopt(adver_chain = self.adver_chain, honest_chain = self.honest_chain)
        attack_mine,block = self.behavior.mine(miner_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain,
                                         global_chain = self.global_chain, 
                                         consensus = self.adver_consensus,
                                         round = round)
        if attack_mine:
            self.behavior.upload(network = self.network, 
                                 adver_chain = self.adver_chain,
                                 current_miner = current_miner, 
                                 round = round,
                                 miner_list = self.adver_list,
                                 fork_block = self._fork_block)
        else:
            self.behavior.wait()

    def clear_record_stage(self,round):
        ## 3. clear and record stage
        self.behavior.clear(miner_list = self.adver_list)# 清空
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
        
        
    def info_getter(self):
        
        loop_block = self.global_chain.last_block
        main_chain_height = loop_block.height
        adver_block_num = 0
        while(loop_block):
            if loop_block.isAdversaryBlock:
                adver_block_num += 1
            loop_block = loop_block.parentblock
        return {'Success Rate': '{:.4f}'.format(adver_block_num/main_chain_height),
                'Theory rate in SynchronousNetwork': '{:.4f}'.format(len(self.adver_list)/len(self.miner_list))}
    

    def resultlog2txt(self,round):
        if self._simplifylog != self._log:
            self._simplifylog = copy.deepcopy(self._log)
            ATTACK_RESULT_PATH = global_var.get_attack_result_path()
            with open(ATTACK_RESULT_PATH / f'Attack Log.txt','a') as f:
                print(self._log,round, '\n',file=f)


