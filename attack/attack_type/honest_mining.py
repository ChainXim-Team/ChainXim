'''
定义honestminging攻击
'''
import attack.attack_type as aa
import random, global_var
class HonestMining(aa.AttackType):
    '''
    算力攻击
    '''
    def __init__(self) -> None:
        super().__init__()
        self.__log = {
            'round': 0,
            'honest_chain': None,
            'adver_chain': None
        }

    def excute_this_attack_per_round(self, round):
        # bh = self.__behavior # 将行为方法类对象赋给一个变量 方便书写
                # 
        # 作为轮进行的chainxim, 每一轮执行时都要简介掌握当前局势, 输入round算是一个了解环境的维度
        # 每轮固定更新攻击状态
        current_miner = random.choice(self.adver_list)       
        newest_block, mine_input = self.behavior.renew(miner_list = self.adver_list, \
                                 honest_chain = self.honest_chain,round = round)
        self.behavior.adopt(adver_chain = self.adver_chain, honest_chain = self.honest_chain)
        attack_mine = self.behavior.mine(miner_list = self.adver_list, current_miner = current_miner \
                              , miner_input = mine_input,\
                              adver_chain = self.adver_chain, \
                                global_chain = self.global_chain, consensus = self.adver_consensus)
        if attack_mine:
            self.behavior.upload(network_type = self.network_type, adver_chain = self.adver_chain, \
               current_miner = current_miner, round = round)
        else:
            self.behavior.wait()
        self.behavior.clear(miner_list = self.adver_list)# 清空
        self.__log['round'] = round
        self.__log['honest_chain'] = self.honest_chain.lastblock.name + ' Height:' + str(self.honest_chain.lastblock.height)
        self.__log['adver_chain'] = self.adver_chain.lastblock.name + ' Height:' + str(self.adver_chain.lastblock.height)
        self.resultlog2txt()
        
    def info_getter(self):
        
        loop_block = self.global_chain.lastblock
        main_chain_height = loop_block.height
        adver_block_num = 0
        while(loop_block):
            if loop_block.isAdversaryBlock:
                adver_block_num += 1
            loop_block = loop_block.last
        return {'Success Rate': '%.4f'% adver_block_num/main_chain_height,
                'Theory rate in SynchronousNetwork': '%.4f'% len(self.adver_list)/len(self.miner_list)}
    

    def resultlog2txt(self):
        ATTACK_RESULT_PATH = global_var.get_attack_result_path()
        with open(ATTACK_RESULT_PATH / f'Attack Log.txt','a') as f:
            print(self.__log, '\n',file=f)


