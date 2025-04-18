import random
from abc import ABCMeta, abstractmethod

import consensus
import miner.miner as miner
import network
from attack import attack_type as at
from data import Chain
from functions import for_name
import global_var
import copy


class Adversary(metaclass=ABCMeta): 
    @abstractmethod
    def __init__(self,**args) -> None:
        self.__Miner_ID = -1 #矿工ID
        self.__adver_setter(**args)
        self.__adver_gener()
        self.__consensus_q_init()
        self.__attack_type_init()
    
    def __adver_setter(self, **args):
        '''
        Adversary对象 成员变量初始化
        '''
        self.__adver_num: int = (args.get('adver_num') if args.get('adver_num') is not None \
                else 0)
        
        self.__attack_type: at.AttackType = for_name('attack.attack_type.' + args.get('attack_type'))() if args.get('attack_type') is not None  \
                else at.HonestMining

        self.__excute_attack: at.AttackType = self.__attack_type
        
        self.__adver_ids: list = list(args.get('adversary_ids')) if args.get('adversary_ids') is not None \
                else []

        self.__miner_list: list[miner.Miner] = args.get('miner_list')

        self.__global_chain:Chain = args.get('global_chain')

        self.__adver_consensus_param: dict = args.get('adver_consensus_param')

        self.__consensus_type: consensus.Consensus = for_name(args.get('consensus_type'))(self.__Miner_ID, self.__adver_consensus_param)

        self.__attack_arg:dict = eval(args.get('attack_arg')) if args.get('attack_arg') is not None else None
        

       
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
                    self.__adver_ids.append(adversary.miner_id)
        if 'Eclipse' in global_var.get_attack_execute_type():
            self.__eclipsed_list_ids = [self.__miner_list[i].miner_id for i in list(self.__attack_arg.get('eclipse_target'))]
        else:
            self.__eclipsed_list_ids = None
        self.__adver_num = len(self.__adver_list)
        return self.__adver_list    
    
    def __consensus_q_init(self):
        # 初始化Adversary的共识
        self.__consensus_type.q = sum([attacker.consensus.q for attacker in self.__adver_list])


    def __attack_type_init(self):
        self.honest_chain: Chain = copy.deepcopy(self.__global_chain)
        '''
        拷贝全局链初始状态作为adver的初始诚实链
        '''
        self.__attack_type.set_init(honest_chain = self.honest_chain, 
                                    adver_list = self.__adver_list,
                                    adver_consensus = self.__consensus_type, 
                                    attack_arg = self.__attack_arg,
                                    eclipsed_list_ids = self.__eclipsed_list_ids)
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
    
    def get_adver_q(self):
        return self.__consensus_type.q
    
    def get_eclipsed_ids(self):
        if self.__eclipsed_list_ids:
            return self.__eclipsed_list_ids
        else:
            return None
    '''
    以下为非构造器
    用于Adversary的进阶功能
    '''
    def excute_per_round(self,round):
        '''
        Adversary的核心功能 每轮执行一次attack
        '''
        self.__excute_attack.excute_this_attack_per_round(round)
        self.__global_chain.add_block_forcibly(self.__attack_type.adver_chain.last_block)
        

    def get_info(self):
        '''
        调用attack中的各种参数计算
        '''
        if len(self.__adver_list) != 0:
            return self.__attack_type.info_getter(miner_num = len(self.__miner_list))
        else:
            return None

