from abc import ABCMeta, abstractmethod
import consensus
import network
import miner
from attack import attackType
from functions import for_name
import random, chain
class Adversary(metaclass=ABCMeta): 
    @abstractmethod
    def __init__(self,**args) -> None:
        self.__Miner_ID = -1 #矿工ID
        self.__isAdversary = True
        self.__adverSetter(**args)
        self.__adverGener()
        self.__consensusQInit()
        self.__attackTypeInit()
    
    def __adverSetter(self, **args):
        '''
        Adversary对象 成员变量初始化
        '''
        '''
        attackParam:dict={
                'adverNum': 0,
                'attackType': 'HonestMining',
                'adversaryIds': [0],
                'networkType': network.TopologyNetwork,
                'consensusType': consensus.PoW,
                'minerList':[miner.Miner],
            }
            '''
        self.__adverNum: int = args.get('adverNum') if args.get('adverNum') is not None \
                else 0
        self.__attackType: attackType.AttackType = for_name('attack.attackType.' + args.get('attackType'))() if args.get('attackType') is not None \
                else attackType.HonestMining
        
        self.__eclipse: bool = args.get('eclipse') if args.get('eclipse') is not None \
                else False
        
        self.__adverIds: list = list(args.get('adversaryIds')) if args.get('adversaryIds') is not None \
                else []
        
        self.__networkType: network.Network = args.get('networkType')

        self.__minerList: list[miner.Miner] = args.get('minerList')

        self.__globalChain:chain.Chain = args.get('globalChain')

        self.__adverConsensusParam: dict = args.get('adverConsensusParam')

        str1 = args.get('consensusType')
        self.__consensusType: consensus.Consensus = for_name(args.get('consensusType'))(self.__Miner_ID, self.__adverConsensusParam)
        

       
    def __adverGener(self):
        '''
        根据传参arg 设置adverMiners 返回 list[miner]
        '''
        self.__adverList: list[miner.Miner] = []
        if len(self.__adverIds) != 0 :
            # 如果ID非空 根据ID设置指定恶意节点
            for Id in list(self.__adverIds):
                self.__adverList.append(self.__minerList[Id])
                self.__minerList[Id].set_adversary(True)
        else:
            if self.__adverNum != 0:
                # 如果ID空 但 攻击者数非0 随机设置恶意节点
                self.__adverList = random.sample(self.__minerList, self.__adverNum)
                for adversary in self.__adverList:
                    adversary.set_adversary(True)
                    self.__adverIds.append(adversary.Miner_ID)
            else:
                # 如果ID空 且 攻击者数为0 不设置恶意节点 返回None
                self.__adverList = None
        return self.__adverList    
    
    def __consensusQInit(self):
        # 初始化Adversary的共识
        '''
        adver_consensus_param = {'q_ave': self.q_adver, 'q_distr':'equal', 
                                 'target': temp_miner.consensus.target}
        '''
        self.__consensusType.q = sum([attacker.consensus.q for attacker in self.__adverList])


    def __attackTypeInit(self):
        self.__attackType.setInit(globalChain = self.__globalChain, minerList = self.__minerList, adverList = self.__adverList, \
                                  networkType = self.__networkType, adverConsensus = self.__consensusType)
    '''
    相关值返回 构造器
    '''
    def getAdverIds(self):
        return self.__adverIds
    
    def getAdverNum(self):
        return self.__adverNum
    
    def getAttackType(self):
        return self.__attackType.__name__
    
    def getEclipse(self):
        return self.__eclipse
    
    def getAdverQ(self):
        return self.__consensusType.q
    
    def getConsensusParam(self):
        pass
    
    '''
    以下为非构造器
    用于返回Adversary进阶参数
    '''
    def excutePerRound(self,round):
        '''
        Adversary的核心功能 每轮执行一次attack
        '''
        self.__attackType.excuteThisAttackPerRound(round)

    def getInfo(self):
        if len(self.__adverList) != 0:
            return self.__attackType.infoGetter()
        else:
            return None

