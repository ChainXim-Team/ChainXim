from abc import ABCMeta, abstractmethod
from attack.attackType.AtomizationBehaviorGroup import BehaviorGroup
import chain, copy, miner, network, consensus
'''
设计攻击类型的抽象类
创建BehaviorGroup实例对象 作为其行为组
'''

class AttackType(metaclass=ABCMeta): 

    def __init__(self) -> None:
        # 定义该攻击类型的原子行为组
        self.__setBehaviorInit()

    def __setBehaviorInit(self):
        self.behavior = BehaviorGroup()


    def setInit(self, globalChain: chain.Chain, adverList:list[miner.Miner], minerList:list[miner.Miner], \
                networkType: network.Network, adverConsensus: consensus.Consensus):
        self.globalChain: chain.Chain = globalChain
        self.honestChain: chain.Chain = copy.deepcopy(globalChain)
        self.minerList: list[miner.Miner] = minerList
        self.adverList: list[miner.Miner] = adverList
        self.networkType: network.Network = networkType
        self.adverConsensus: consensus.Consensus = adverConsensus
        self.adverChain: chain.Chain = self.adverConsensus.Blockchain
        

    @abstractmethod
    def excuteThisAttackPerRound(self,round):
        pass

    @abstractmethod
    def infoGetter(self):
        pass


