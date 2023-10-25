from abc import ABCMeta, abstractmethod
from functions import for_name
from attack import attack_type as at
import chain, consensus, network, miner
import random
class Adversary(metaclass=ABCMeta): 
    @abstractmethod
    def __init__(self,**args) -> None:
        self.__Miner_ID = -1 #矿工ID
        self.__isAdversary = True
        self.__adver_setter(**args)
        self.__adver_gener()
        self.__consensus_q_init()
        self.__attack_type_init()
    
    def __adver_setter(self, **args):
        '''
        Adversary对象 成员变量初始化
        '''
        '''
        attackParam:dict={
                'adver_num': 0,
                'attack_type': 'HonestMining',
                'adversaryIds': [0],
                'network_type': network.TopologyNetwork,
                'consensus_type': consensus.PoW,
                'miner_list':[miner.Miner],
            }
            '''
        self.__adver_num: int = args.get('adver_num') if args.get('adver_num') is not None \
                else 0

        self.__eclipse: bool = args.get('eclipse') if args.get('eclipse') is not None \
                else False
        
        self.__attack_type: at.AttackType = for_name('attack.attack_type.' + args.get('attack_type'))() if args.get('attack_type') is not None  \
                else at.HonestMining
        
        self.__eclipse_attack: at.AttackType = at.Eclipse(self.__attack_type) if self.__eclipse else None

        print(self.__eclipse_attack)

        
        self.__adver_ids: list = list(args.get('adversary_ids')) if args.get('adversary_ids') is not None \
                else []
        
        self.__network_type: network.Network = args.get('network_type')

        self.__miner_list: list[miner.Miner] = args.get('miner_list')

        self.__global_chain:chain.Chain = args.get('global_chain')

        self.__adver_consensus_param: dict = args.get('adver_consensus_param')

        self.__consensus_type: consensus.Consensus = for_name(args.get('consensus_type'))(self.__Miner_ID, self.__adver_consensus_param)

        self.__attack_arg:dict = eval(args.get('attack_arg'))
        

       
    def __adver_gener(self):
        '''
        根据传参arg 设置adverMiners 返回 list[miner]
        '''
        self.__adver_list: list[miner.Miner] = []
        if len(self.__adver_ids) != 0 :
            # 如果ID非空 根据ID设置指定恶意节点
            for Id in list(self.__adver_ids):
                self.__adver_list.append(self.__miner_list[Id])
                self.__miner_list[Id].set_adversary(True)
        else:
            if self.__adver_num != 0:
                # 如果ID空 但 攻击者数非0 随机设置恶意节点
                self.__adver_list = random.sample(self.__miner_list, self.__adver_num)
                for adversary in self.__adver_list:
                    adversary.set_adversary(True)
                    self.__adver_ids.append(adversary.Miner_ID)
            else:
                # 如果ID空 且 攻击者数为0 不设置恶意节点 返回None
                self.__adver_list = None
        return self.__adver_list    
    
    def __consensus_q_init(self):
        # 初始化Adversary的共识
        '''
        adver_consensus_param = {'q_ave': self.q_adver, 'q_distr':'equal', 
                                 'target': temp_miner.consensus.target}
        '''
        self.__consensus_type.q = sum([attacker.consensus.q for attacker in self.__adver_list])


    def __attack_type_init(self):
        self.__attack_type.set_init(global_chain = self.__global_chain, miner_list = self.__miner_list, adver_list = self.__adver_list, \
                                  network_type = self.__network_type, adver_consensus = self.__consensus_type, attack_arg = self.__attack_arg)
    '''
    相关值返回 构造器
    '''
    def get_adver_ids(self):
        return self.__adver_ids
    
    def get_adver_num(self):
        return self.__adver_num
    
    def get_attack_type_name(self):
        return self.__attack_type.__class__.__name__
    
    def get_attack_type(self):
        return self.__attack_type
    
    def get_eclipse(self):
        return self.__eclipse
    
    def get_adver_q(self):
        return self.__consensus_type.q
    
    def get_consensus_param(self):
        pass
    
    '''
    以下为非构造器
    用于Adversary的进阶功能
    '''
    def excute_per_round(self,round):
        '''
        Adversary的核心功能 每轮执行一次attack
        '''
        self.__attack_type.excute_this_attack_per_round(round)

    def get_info(self):
        '''
        调用attack中的各种参数计算
        '''
        if len(self.__adver_list) != 0:
            return self.__attack_type.info_getter()
        else:
            return None

