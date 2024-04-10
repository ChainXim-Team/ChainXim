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


    def set_init(self, global_chain: Chain, adver_list:list[miner.Miner], miner_list:list[miner.Miner], \
                network_type: network.Network, adver_consensus: consensus.Consensus, attack_arg:dict):
        self.global_chain: Chain = global_chain
        self.honest_chain: Chain = copy.deepcopy(global_chain)
        self.honest_chain.add_blocks(blocks=[global_chain.get_last_block()])
        self.miner_list: list[miner.Miner] = miner_list
        self.adver_list: list[miner.Miner] = adver_list
        self.network: network.Network = network_type
        self.adver_consensus: consensus.Consensus = adver_consensus
        self.adver_chain: Chain = self.adver_consensus.local_chain
        self.attack_arg:dict = attack_arg

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


