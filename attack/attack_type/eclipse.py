'''
定义honestminging攻击
'''
import copy
import random

import attack.attack_type as aa
import global_var
from data import Block, Chain
from miner._consts import FLOODING, OUTER, SELF, SELFISH, SPEC_TARGETS

attack_type= aa.HonestMining

# 默认继承HonestMining

class Eclipse(aa.AttackType):
    '''
    日蚀攻击
    '''
    # def __init__(self,attack_obj:aa.AttackType) -> None:
    #     super().__init__()
    #     self.__attack_obj = attack_obj

    # def renew_stage(self, round):
    #     newest_block, miner_input = self.__attack_obj.renew_stage(round)
    #     return newest_block, miner_input

    # def attack_stage(self, round, mine_input):
    #     self.__attack_obj.attack_stage(round,mine_input)

    # def clear_record_stage(self, round):
    #     self.__attack_obj.clear_record_stage(round)


    # def excute_this_attack_per_round(self,round):
    #     # probe during the renew stage
    #     newest_block, miner_input = self.renew_stage(round)
    #     self.attack_stage(round, mine_input= miner_input)
    #     # eclipse after the attack stage
    #     self.clear_record_stage(round)

    
    # def info_getter(self):
    #     self.__attack_obj.info_getter()
    def __init__(self) -> None:
        super().__init__()
        self._log = {
            'honest_chain': None,
            'adver_chain': None,
            'eclipse_block': None,
            'fork_block': None,
        }
        self._fork_block: Block = None
        self._simplifylog = {}
        self._eclipse_block: Block = None # 记录 eclipse对象的newestblock状况
        

    def renew_stage(self,round):
        ## 1. renew stage
        newest_block, mine_input, imcoming_block_from_eclipse = self.behavior.renew(miner_list = self.adver_list, 
                                    honest_chain = self.honest_chain,round = round,eclipse_list_ids=self.eclipsed_list_ids)
        
        # renew eclipse part
        self._eclipse_block = self._eclipse_block if self._eclipse_block!= None else self.honest_chain.head
        newest_block_from_eclipse = self._eclipse_block
        if len(imcoming_block_from_eclipse) >0:
            for hash,block in imcoming_block_from_eclipse.items():
                    if block.get_height() > newest_block_from_eclipse.get_height():
                        newest_block_from_eclipse = block
            self._eclipse_block = newest_block_from_eclipse

        return newest_block, mine_input
    
    def attack_stage(self,round,mine_input,newest_block:Block):
        ## 2. attack stage
        current_miner = random.choice(self.adver_list)


        # 将A与Ve同步 A>=V
        eclipse_height = self._eclipse_block.height
        adver_height = self.adver_chain.get_height()
        domain_flag = False
        if eclipse_height > adver_height:
            if self.__judge_block_from(self._eclipse_block).blockhead.miner in self.adver_list_ids:
                self.adver_chain._add_block_forcibly(self._eclipse_block)
            else:
                pass
        elif eclipse_height < adver_height:
            domain_flag = True
            pass
        else:
            domain_flag = True
            pass
        
        
        # 将A与Vh同步 Vh=A>=V
        honest_height = self.honest_chain.get_height()
        adver_height = self.adver_chain.get_height()
        upload_flag = False
        if honest_height > adver_height:
            self._fork_block = self.behavior.adopt(adver_chain = self.adver_chain, honest_chain = self.honest_chain)
        else:
            pass
        

        # 开挖
        attack_mine,admin_block = self.behavior.mine(miner_list = self.adver_list,
                                                     current_miner = current_miner,
                                                     miner_input = mine_input,
                                                     adver_chain = self.adver_chain,
                                                     global_chain = self.global_chain,
                                                     consensus = self.adver_consensus,
                                                     round = round)
        if attack_mine or not domain_flag or (adver_height > honest_height and not domain_flag):
            self.behavior.upload(network = self.network,
                                 adver_chain = self.adver_chain,
                                 current_miner = current_miner,
                                 round = round,
                                 miner_list = self.adver_list,
                                 fork_block = self._fork_block)
            for miner in self.adver_list:
                miner.consensus.local_chain._add_block_forcibly(self.adver_chain.get_last_block())
        elif domain_flag:
            for miner in self.eclipsed_list:
                miner.consensus.local_chain._add_block_forcibly(self.adver_chain.get_last_block())
                self._eclipse_block = miner.consensus.local_chain.get_last_block()




        '''        
        eclipse_flag = False

        newest_block_from_eclipse = self.adver_chain.head if self._eclipse_block == None else self._eclipse_block
        if self.honest_chain.get_height() > self.adver_chain.get_height():
            # 如果外部链比攻击链高 则更新到adverchain 但是不包括 来自eclipse的区块
            self._fork_block = self.behavior.adopt(adver_chain = self.adver_chain, honest_chain = self.honest_chain)
        
            # 判断来自eclipse的区块的情况
            
            if len(imcoming_block_from_eclipse) >0 :
                for k,v in imcoming_block_from_eclipse.items():
                    if v.get_height() > newest_block_from_eclipse.get_height():
                        newest_block_from_eclipse = v
                self._eclipse_block = newest_block_from_eclipse


            if newest_block_from_eclipse.get_height() > self.adver_chain.get_height():

                if self.__judge_block_from(newest_block_from_eclipse).blockhead.miner in self.adver_list_ids:
                # 如果最新区块自攻击者的区块挖出来则接受
                    self.adver_chain._add_block_forcibly(newest_block_from_eclipse)
                    attack_mine,admin_block = self.behavior.mine(miner_list = self.adver_list,
                                                                 current_miner = current_miner,
                                                                 miner_input = mine_input,
                                                                 adver_chain = self.adver_chain,
                                                                 global_chain = self.global_chain, 
                                                                 consensus = self.adver_consensus,
                                                                 round = round)
                    self.behavior.upload(network = self.network, 
                                         adver_chain = self.adver_chain,
                                         current_miner = current_miner, 
                                         round = round,
                                         miner_list = self.adver_list,
                                         fork_block = self._fork_block)
                else:
                    attack_mine,admin_block = self.behavior.mine(miner_list = self.adver_list,
                                                                 current_miner = current_miner,
                                                                 miner_input = mine_input,
                                                                 adver_chain = self.adver_chain,
                                                                 global_chain = self.global_chain, 
                                                                 consensus = self.adver_consensus,
                                                                 round = round)
                    for ec_miner in self.eclipsed_list:
                        ec_miner.consensus.local_chain._add_block_forcibly(self.adver_chain.get_last_block())
            else:
                attack_mine,admin_block = self.behavior.mine(miner_list = self.adver_list,
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
                    for ec_miner in self.eclipsed_list:
                        ec_miner.consensus.local_chain._add_block_forcibly(self.adver_chain.get_last_block())         
        else:
            # 判断来自eclipse的区块的情况
            if len(imcoming_block_from_eclipse) >0:
                for k,v in imcoming_block_from_eclipse.items():
                    if v.get_height() > newest_block_from_eclipse.get_height():
                        newest_block_from_eclipse = v
            self._eclipse_block = newest_block_from_eclipse

            
            if newest_block_from_eclipse.get_height() <= self.adver_chain.get_height():
                    attack_mine,admin_block = self.behavior.mine(miner_list = self.adver_list,
                                                                 current_miner = current_miner,
                                                                 miner_input = mine_input,
                                                                 adver_chain = self.adver_chain,
                                                                 global_chain = self.global_chain, 
                                                                 consensus = self.adver_consensus,
                                                                 round = round)
                    self.behavior.upload(network = self.network, 
                                         adver_chain = self.adver_chain,
                                         current_miner = current_miner, 
                                         round = round,
                                         miner_list = self.adver_list,
                                         fork_block = self._fork_block)
            else:
                if newest_block_from_eclipse.blockhead.miner in self.adver_list_ids:
                    self.adver_chain._add_block_forcibly(newest_block_from_eclipse)
                    attack_mine,admin_block = self.behavior.mine(miner_list = self.adver_list,
                                                                 current_miner = current_miner,
                                                                 miner_input = mine_input,
                                                                 adver_chain = self.adver_chain,
                                                                 global_chain = self.global_chain, 
                                                                 consensus = self.adver_consensus,
                                                                 round = round)
                    self.behavior.upload(network = self.network, 
                                         adver_chain = self.adver_chain,
                                         current_miner = current_miner, 
                                         round = round,
                                         miner_list = self.adver_list,
                                         fork_block = self._fork_block)
                else:
                    attack_mine,admin_block = self.behavior.mine(miner_list = self.adver_list,
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
        '''




    def clear_record_stage(self,round):
        ## 3. clear and record stage
        self.behavior.clear(miner_list = self.adver_list)# 清空
        # self._log['round'] = round
        self._log['honest_chain'] = self.honest_chain.last_block.name + ' Height:' + str(self.honest_chain.last_block.height)
        self._log['adver_chain'] = self.adver_chain.last_block.name + ' Height:' + str(self.adver_chain.last_block.height)
        self._log['eclipse_block'] = self._eclipse_block.name  + ' Height:' + str(self._eclipse_block.height)
        self._log['fork_block'] = self._fork_block.name if self._fork_block is not None else self.adver_chain.head.name
        self.resultlog2txt(round)


    def excute_this_attack_per_round(self, round):
        
        ## 1. renew stage
        newest_block, mine_input = self.renew_stage(round)
        ## 2. attack stage
        self.attack_stage(round, mine_input, newest_block)
        ## 3. clear and record stage
        self.clear_record_stage(round)
    

    def __judge_block_from(self,block:Block) -> Block:
        while block!=None and block.blockhead.miner in self.eclipsed_list_ids :
            block = block.parentblock
            if block.blockhead.miner in self.adver_list_ids:
                break
        return block
        
    def info_getter(self):
        
        loop_block = self.global_chain.last_block
        main_chain_height = loop_block.height
        adver_block_num = 0
        tmp_eclipse = 0
        eclipse_block = 0
        all_eclipse_block = 0
        eclipse_blocks = []
        all_eclipse_blocks = []
        tmp_blocks = []
        while(loop_block):
            if loop_block.isAdversaryBlock:
                adver_block_num += 1
                eclipse_block += tmp_eclipse
                eclipse_blocks.extend(tmp_blocks)
                tmp_eclipse = 0
                tmp_blocks = []
                
            else:
                if loop_block.blockhead.miner in self.eclipsed_list_ids:
                    tmp_eclipse +=1
                    tmp_blocks.append(loop_block)
                    all_eclipse_block += 1
                    all_eclipse_blocks.append(loop_block)
                else:
                    tmp_eclipse = 0
                    tmp_blocks = []
            loop_block = loop_block.parentblock
        

        all_blocks_from_eclipse = []
        for hash,block in self.global_chain.block_set.items():
            if block.blockhead.miner in self.eclipsed_list_ids:
                all_blocks_from_eclipse.append(block)
                    

        ATTACK_RESULT_PATH = global_var.get_attack_result_path()
        with open(ATTACK_RESULT_PATH / f'Attack Log result.txt','a') as f:
                print('eclipse block:', '\n',file=f)
                for eb in eclipse_blocks:
                    print(eb.name, '\n',file=f)
                print('all eclipse block:', '\n',file=f)
                for eb in all_eclipse_blocks:
                    print(eb.name, '\n',file=f)
        
        miner_num = len(self.miner_list)
        eclipse_rate = len(self.eclipsed_list)/miner_num
        adversart_rate = len(self.adver_list)/miner_num
        return {'Number of Adversary blocks': '{}'.format(adver_block_num),
                'Number of blocks eclipsed by adversary': '{}'.format(eclipse_block),
                'Number of blocks generated by eclipsed miners': '{}'.format(len(all_blocks_from_eclipse)),
                'Utilization rate of eclipse blocks': '{:.5f}'.format(eclipse_block/len(all_blocks_from_eclipse)),
                'Equivalent improvement of adversary': '{:.5f}'.format((adver_block_num+eclipse_block)/main_chain_height),
                'Recommended equivalent improvement of adversary ': '{:.5f}'.format(adversart_rate/(1-eclipse_rate)),
                # 'Union attack by adversary and eclipsed miner:': '{}'.format((adver_block_num+eclipse_block)/main_chain_height),
                # 'Reference rate': '{:.4f}'.format((len(self.adver_list)+len(self.eclipsed_list))/len(self.miner_list))
                }
    

    def resultlog2txt(self,round):
        if self._simplifylog != self._log:
            self._simplifylog = copy.deepcopy(self._log)
            ATTACK_RESULT_PATH = global_var.get_attack_result_path()
            with open(ATTACK_RESULT_PATH / f'Attack Log.txt','a') as f:
                print(self._log, round,'\n',file=f)



