'''
定义honestminging攻击
'''
import attack.attack_type as aa
attack_type= aa.HonestMining

# 默认继承HonestMining

class Eclipse(aa.AttackType):
    '''
    日蚀攻击
    '''
    def __init__(self,attack_obj:aa.AttackType) -> None:
        super().__init__()
        self.__attack_obj = attack_obj


    def excute_this_attack_per_round(self,round):
        self.__attack_obj.excute_this_attack_per_round(round= round)

    
    def info_getter(self):
        self.__attack_obj.info_getter()




