'''
定义honestminging攻击
'''
from attack.attackType.AttackType import AttackType
import random, global_var
class HonestMining(AttackType):
    '''
    算力攻击
    '''
    def __init__(self) -> None:
        super().__init__()
        self.__name__ = 'HonestMining'
        self.__log = {
            'round': 0,
            'HonestChain': None,
            'AdverChain': None
        }

    def excuteThisAttackPerRound(self, round):
        # bh = self.__behavior # 将行为方法类对象赋给一个变量 方便书写
                # 
        # 作为轮进行的chainxim, 每一轮执行时都要简介掌握当前局势, 输入round算是一个了解环境的维度
        # 每轮固定更新攻击状态
        currentMiner = random.choice(self.adverList)       
        newestBlock, mineInput = self.behavior.renew(minerList = self.adverList, \
                                 honestChain = self.honestChain,round = round)
        attack_mine = self.behavior.mine(minerList = self.adverList, currentMiner = currentMiner \
                              , minerInput = mineInput,\
                              adverChain = self.adverChain, \
                                globalChain = self.globalChain, consensus = self.adverConsensus)
        self.behavior.clear(minerList = self.adverList)# 清空
        self.behavior.adopt(adverChain = self.adverChain, honestChain = self.honestChain)
        if attack_mine:
            self.behavior.upload(networkType = self.networkType, adverChain = self.adverChain, \
               currentMiner = currentMiner, round = round)
        else:
            self.behavior.wait()
        
        self.__log['round'] = round
        self.__log['HonestChain'] = self.honestChain.lastblock.name + ' Height:' + str(self.honestChain.lastblock.height)
        self.__log['AdverChain'] = self.adverChain.lastblock.name + ' Height:' + str(self.adverChain.lastblock.height)
        self.resultlog2txt()
        
    def infoGetter(self):
        loopBlock = self.globalChain.lastblock
        mainChainHeight = loopBlock.height
        adverBlockNum = 0
        while(loopBlock):
            if loopBlock.isAdversaryBlock:
                adverBlockNum += 1
            loopBlock = loopBlock.last
        return {'Success Rate': adverBlockNum/mainChainHeight,
                'Theory': len(self.adverList)/len(self.minerList)}
    

    def resultlog2txt(self):
        ATTACK_RESULT_PATH = global_var.get_attack_result_path()
        with open(ATTACK_RESULT_PATH / f'Attack Log.txt','a') as f:
            print(self.__log, '\n',file=f)


