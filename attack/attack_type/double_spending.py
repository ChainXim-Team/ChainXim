'''
定义honestminging攻击
'''
import attack.attack_type as aa
import random, global_var, chain, math
class DoubleSpending(aa.AttackType):
    '''
    算力攻击
    '''
    def __init__(self) -> None:
        super().__init__()
        self.__log = {
            'round': 0,
            'honest_chain': None,
            'adver_chain': None,
            'success': 0,
            'fail':0,
            'behavior':None
        }
        self.__fork_block: chain.Block
        self.__fork_height:int = 0

    def double_spending_main_bulk(self,round):
        bh = self.behavior
        n = self.attack_arg['N']
        ng = self.attack_arg['Ng']
        newest_block, mine_input = bh.renew(miner_list = self.adver_list, \
                                 honest_chain = self.honest_chain,round = round)
        honest_height = self.honest_chain.lastblock.BlockHeight()
        adver_height = self.adver_chain.lastblock.BlockHeight()
        current_miner = random.choice(self.adver_list)
        if honest_height - self.__fork_height < n:
            attack_mine = bh.mine(miner_list = self.adver_list, current_miner = current_miner \
                              , miner_input = mine_input,\
                              adver_chain = self.adver_chain, \
                                global_chain = self.global_chain, consensus = self.adver_consensus)
            self.__log['behavior'] = 'conforming ' + str(honest_height - self.__fork_height) + '/' +str(n)
        elif honest_height - self.__fork_height >= n:
            if honest_height - adver_height >= ng:
            # 攻击链比诚实链落后Ng个区块
                self.__fork_block = bh.adopt(adver_chain = self.adver_chain, honest_chain = self.honest_chain)
                self.__fork_height = self.__fork_block.BlockHeight()
                attack_mine = bh.mine(miner_list = self.adver_list, current_miner = current_miner \
                              , miner_input = mine_input,\
                              adver_chain = self.adver_chain, \
                                global_chain = self.global_chain, consensus = self.adver_consensus) 
                if self.__log['behavior'] != 'adopt':
                    self.__log['fail'] = self.__log['fail'] + 1
                self.__log['behavior'] = 'adopt'
            elif adver_height > honest_height:
                block = bh.upload(network_type = self.network_type, adver_chain = self.adver_chain, \
                        current_miner = current_miner, round = round)
                attack_mine = bh.mine(miner_list = self.adver_list, current_miner = current_miner \
                              , miner_input = mine_input,\
                              adver_chain = self.adver_chain, \
                                global_chain = self.global_chain, consensus = self.adver_consensus)
                if attack_mine:
                    block = bh.upload(network_type = self.network_type, adver_chain = self.adver_chain, \
               current_miner = current_miner, round = round)
                if self.__log['behavior'] != 'override':
                    self.__log['success'] = self.__log['success'] + 1
                self.__log['behavior'] = 'override'
            else:
                attack_mine = bh.mine(miner_list = self.adver_list, current_miner = current_miner \
                              , miner_input = mine_input,\
                              adver_chain = self.adver_chain, \
                                global_chain = self.global_chain, consensus = self.adver_consensus)
                self.__log['behavior'] = 'matching'
        

    def excute_this_attack_per_round(self, round):
        '''双花攻击'''
        self.double_spending_main_bulk(round)
        bh = self.behavior
        self.__log['honest_chain']=self.honest_chain.lastblock.name,self.honest_chain.lastblock.height
        self.__log['adver_chain']=self.adver_chain.lastblock.name,self.adver_chain.lastblock.height
        #self.log['other']=self.log['other']+' fork block is '+self.fork_blockname
        bh.clear(miner_list = self.adver_list)# 清空
        #self.resultlog2txt()
        
    def info_getter(self):

        rate, thr_rate = self.__success_rate()
        return {'Success Rate': '%.4f'% rate,
                'Theory rate in SynchronousNetwork': '%.4f'% thr_rate,
                'Attack times': self.__log['success']+self.__log['fail'],
                'Success times': self.__log['success'],
                'Ng': self.attack_arg['Ng'],
                'N': self.attack_arg['N']
                }
    
    def __success_rate(self):
        if self.__log['success'] != 0 or self.__log['fail'] != 0:
            rate = self.__log['success']/(self.__log['success']+self.__log['fail'])
            ## 计算理论成功率
            tmp = 0
            n = self.attack_arg['N']
            ng = self.attack_arg['Ng']
            beta = len(self.adver_list)/(len(self.miner_list)-len(self.adver_list))
            if ng > 100*n:
                # Ng 非常大
                if beta >= 1:
                    thr_rate = 1
                else:
                    for j in range(0, n+1):
                        tmp = tmp + (math.factorial(j+n-1))/((math.factorial(j))*(math.factorial(n-1)))\
                        *((1/(1+beta))**n)*((beta/(1+beta))**j)*(1-beta**(n-j+1))
                    thr_rate = 1-tmp
            else:
                # Ng 正常
                if beta == 1:
                    for j in range(0, n+1):
                        1/(2**(n+j))*(math.factorial(j+n-1))/((math.factorial(j))*(math.factorial(n-1)))*((n-j+1)/(ng+1))
                    thr_rate = 1-tmp
                else:
                    for j in range(0, n+1):
                        tmp = tmp + (math.factorial(j+n-1))/((math.factorial(j))*(math.factorial(n-1)))\
                        *((1/(1+beta))**n)*((beta/(1+beta))**j)*((1-beta**(n-j+1))/(1-beta**(ng+1)))
                    thr_rate = 1-tmp
            ##
            return rate, thr_rate
        else:
            return False
        
    def resultlog2txt(self):
        ATTACK_RESULT_PATH = global_var.get_attack_result_path()
        with open(ATTACK_RESULT_PATH / f'Attack Log.txt','a') as f:
            print(self.__log, '\n',file=f)


