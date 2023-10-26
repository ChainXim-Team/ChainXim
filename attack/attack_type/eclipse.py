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

    def renew_stage(self, round):
        newest_block, miner_input = self.__attack_obj.renew_stage(round)
        return newest_block, miner_input

    def attack_stage(self, round, mine_input):
        self.__attack_obj.attack_stage(round,mine_input)

    def clear_record_stage(self, round):
        self.__attack_obj.clear_record_stage(round)


    def excute_this_attack_per_round(self,round):
        # probe during the renew stage
        newest_block, miner_input = self.renew_stage(round)
        self.attack_stage(round, mine_input= miner_input)
        # eclipse after the attack stage
        self.clear_record_stage(round)

    
    def info_getter(self):
        self.__attack_obj.info_getter()




