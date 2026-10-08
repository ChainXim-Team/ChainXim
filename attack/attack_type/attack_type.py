import copy
from abc import ABCMeta, abstractmethod

import attack.attack_type.atomization_behavior as ab
import consensus
import miner.miner as miner
import network
from data import Block, Chain

'''
设计攻击类型的抽象类
创建BehaviorGroup实例对象 作为其行为组
'''

class AttackType(metaclass=ABCMeta): 

    def __init__(self) -> None:
        # 定义该攻击类型的原子行为组
        self.__set_behavior_init()

    def __set_behavior_init(self):
        self.behavior = ab.AtomizationBehavior()


    def set_init(self, global_chain_prp: Chain, global_chain_vt: list[Chain], adver_list:list[miner.Miner], miner_list:list[miner.Miner], \
                network_type: network.Network, adver_consensus: consensus.Consensus, attack_arg:dict, prpchain_update: Chain, \
                    eclipsed_list:list[miner.Miner] = None):
        self.global_chain_prp: Chain = global_chain_prp
        self.honest_chain_prp: Chain = copy.deepcopy(global_chain_prp)
        self.honest_chain_prp.add_blocks(blocks=[global_chain_prp.get_last_block()])
        self.global_chain_vt: list[Chain] = global_chain_vt
        self.honest_chain_vt: list[Chain] = copy.deepcopy(global_chain_vt)
        for i in range(len(self.honest_chain_vt)):
            self.honest_chain_vt[i].add_blocks(blocks=[global_chain_vt[i].get_last_block()])

        self.miner_list: list[miner.Miner] = miner_list
        self.miner_list_ids: list[int] = [miner.miner_id for miner in self.miner_list]
        self.adver_list: list[miner.Miner] = adver_list
        self.adver_list_ids: list[int] = [miner.miner_id for miner in self.adver_list]


        self.eclipsed_list: list[miner.Miner] = eclipsed_list if eclipsed_list is not None else None
        self.eclipsed_list_ids: list[int] = [miner.miner_id for miner in self.eclipsed_list] if eclipsed_list is not None else None

        # self.otherminer_list: list[miner.Miner] = list(set(miner_list).difference(set(eclipsed_list)).difference(set(adver_list)))
        # self.otherminer_list: list[int] = [miner.miner_id for miner in self.otherminer_list]

        self.network: network.Network = network_type
        self.adver_consensus: consensus.Consensus = adver_consensus
        self.adver_chain_prp: Chain = self.adver_consensus.local_chain_prp
        self.adver_chain_vt: list[Chain] = self.adver_consensus.local_chain_vt
        self.attack_arg:dict = attack_arg

        self.prpchain_update: Chain = prpchain_update

    @abstractmethod
    def renew_stage(self,round):
        ## 1. renew stage
        newest_block:Block
        mine_input:any
        return newest_block, mine_input
    
    @abstractmethod
    def attack_stage(self,round,mine_input):
        ## 2. attack stage
        pass

    @abstractmethod
    def clear_record_stage(self,round):
        ## 3. clear and record stage
        pass

    @abstractmethod
    def excute_this_attack_per_round(self,round):
        pass

    @abstractmethod
    def info_getter(self):
        pass


