'''
定义honestminging攻击
'''
import math
import random

import attack.attack_type as aa
import global_var
from data import Block
from collections import defaultdict
import consensus
import copy

from global_var import set_onetime_double_spending


class DoubleSpending(aa.AttackType):
    '''
    算力攻击
    '''
    def __init__(self) -> None:
        super().__init__()
        self._log = {
            'honest_chain': None,
            'adver_chain': None,
            'success': 0,
            'fail': 0,
            'behavior': [[] for _ in range(global_var.get_vtnum())],
            'behavior_prp': None,
            'fork_block': [None for _ in range(global_var.get_vtnum())],
            'success_vtchain_index':[],
            'fail_vtchain_index': [],
            'fail_num':0
        }
        self._simplifylog = {}
        self._fork_block: list[Block] = [None for _ in range(global_var.get_vtnum())]
        self._fork_height: list[int] = [0 for _ in range(global_var.get_vtnum())]
        self._attackblock = defaultdict(Block)
        self._lastattackblock: list[Block] = [None for _ in range(global_var.get_vtnum())]  # 用于记录上传的最新的attackblock
        self._attack_success_detect: bool = False
        self.attack_flag: bool = False
        self.attack_flag_ready: bool = False
        self.attack_block: Block = None
        self.exec_start = False
        self.upload_prp = False

    def renew_stage(self, round):
        ## 1. renew stage
        bh = self.behavior
        newest_block, mine_input = bh.renew(miner_list = self.adver_list,
                                    honest_chain_prp = self.honest_chain_prp, honest_chain_vt = self.honest_chain_vt, round = round)

        if self._attack_success_detect:
            all_blocks_found = True
            for i in range(global_var.get_vtnum()):
                if not self.honest_chain_vt[i].search_block(self._lastattackblock[i]):
                    all_blocks_found = False
                    break

            if all_blocks_found:
                self._log['success'] += 1
                self._attack_success_detect = False
                self._fork_block = self._lastattackblock.copy()
                self._fork_height = [block.get_height() for block in self._lastattackblock]  # 获取各个链的高度
        return newest_block, mine_input

    def attack_stage(self, round, mine_input):
        bh = self.behavior
        n = self.attack_arg['N']
        ng = self.attack_arg['Ng']
        attack_flag = self.attack_flag

        current_miner = random.choice(self.adver_list)

        attack_mine = False
        attack_mine_flag = False

        if not attack_flag:
            if self.honest_chain_prp.get_height() > self.adver_chain_prp.get_height():
                print('has adopt in prp')
                fork_block = self.behavior.adopt(adver_chain=self.adver_chain_prp, honest_chain=self.honest_chain_prp)
                # self._fork_block.append(fork_block)

            for i in range(len(self.adver_chain_vt)):
                if self.honest_chain_vt[i].get_height() > self.adver_chain_vt[i].get_height():
                    print(f'has adopt in vt{i}')
                    fork_block = self.behavior.adopt(adver_chain=self.adver_chain_vt[i],
                                                     honest_chain=self.honest_chain_vt[i])
                    # self._fork_block.append(fork_block)

            attack_mine, block = self.behavior.mine(miner_list=self.adver_list,
                                                    current_miner=current_miner,
                                                    miner_input=mine_input,
                                                    adver_chain_prp=self.adver_chain_prp,
                                                    global_chain_prp=self.global_chain_prp,
                                                    adver_chain_vt=self.adver_chain_vt,
                                                    global_chain_vt=self.global_chain_vt,
                                                    consensus=self.adver_consensus,
                                                    round=round,
                                                    necessary_blocks=[])
            if attack_mine:
                if block.index == 0:
                    attack_block_tx = block
                    self.behavior.upload(network=self.network,
                                         adver_chain_prp=self.adver_chain_prp,
                                         adver_chain_vt=self.adver_chain_vt,
                                         current_miner=current_miner,
                                         round=round,
                                         miner_list=self.adver_list,
                                         fork_block=[attack_block_tx]
                                         )
                elif block.index == 1:
                    if not self.attack_flag_ready:
                        attack_block_prp = block
                        self.attack_block = attack_block_prp
                        for adv_miner in self.adver_list:
                            adv_miner.consensus.receive_block(self.attack_block)
                        global_var.add_ds_try_times()
                        global_var.set_ds_height(attack_block_prp.height)
                    # if not self.exec_start:
                    #     for block in self.honest_chain_prp:
                    #         if block.isAdversaryBlock == False:
                    #             self.exec_start = True
                    #             break
                    # if self.exec_start:
                    self.attack_flag_ready = True
                    # self.attack_flag = True

                    # for adver_miner in self.miner_list:
                    #     adver_miner.consensus.local_chain_prp.add_blocks(blocks=block)

                    # else :
                    #     self.behavior.upload(network=self.network,
                    #                          adver_chain_prp=self.adver_chain_prp,
                    #                          adver_chain_vt=self.adver_chain_vt,
                    #                          current_miner=current_miner,
                    #                          round=round,
                    #                          miner_list=self.adver_list,
                    #                          fork_block=[attack_block_prp]
                    #                          )

                else:
                    attack_block_vt = block
                    self._fork_block[attack_block_vt.index - 2] = attack_block_vt
                    print('in upload')
                    self.behavior.upload(network=self.network,
                                         adver_chain_prp=self.adver_chain_prp,
                                         adver_chain_vt=self.adver_chain_vt,
                                         current_miner=current_miner,
                                         round=round,
                                         miner_list=self.adver_list,
                                         fork_block=[self._fork_block[attack_block_vt.index - 2]]
                                         )
            else:
                self.behavior.wait()

        if self.attack_flag_ready:
        # 检查honest_chain_prp上有没有和self.attack_block同一高度的块，如果有，就设置self.attack_flag为True
            for block in self.honest_chain_prp:
                if block.height == self.attack_block.height:
                    for adv_miner in self.adver_list:
                        adv_miner.consensus.receive_block(self.attack_block)
                    self.attack_flag = True
                    self.attack_flag_ready = False
                    file_path = f'D:/double-spending_count.txt'  # 请将 'your_file_path_here.txt' 替换为你指定的文件路径
                    with open(file_path, 'a') as f:
                        f.write(f"double-spending start {round}\n")
                    print(f'attack begin at round{round}')
                    print(f'double-spending start')
                    break
        if attack_flag:
            attack_mine, blocks = bh.mine(miner_list=self.adver_list,
                                          current_miner=current_miner,
                                          miner_input=mine_input,
                                          adver_chain_prp=self.adver_chain_prp,
                                          global_chain_prp=self.global_chain_prp,
                                          adver_chain_vt=self.adver_chain_vt,
                                          global_chain_vt=self.global_chain_vt,
                                          consensus=self.adver_consensus,
                                          round=round,
                                          necessary_blocks=[self.attack_block])
            # 获取投票链的高度
            honest_heights_vt = [chain.get_last_block().get_height() for chain in self.honest_chain_vt]
            adver_heights_vt = [chain.get_last_block().get_height() for chain in self.adver_chain_vt]

            if attack_mine:
                print(f'now block index:{blocks.index}')
                if blocks.index == 1:
                    # 更新目标链的行为状态
                    # blocks = bh.upload(network=self.network,
                    #                    adver_chain_prp=self.adver_chain_prp,
                    #                    adver_chain_vt=self.adver_chain_vt,
                    #                    current_miner=current_miner,
                    #                    round=round,
                    #                    miner_list=self.adver_list,
                    #                    fork_block=[blocks] if blocks is not None else
                    #                    [self.honest_chain_prp.head])
                    print(f'now adver mine a prp block')
                    if self._log['behavior_prp'] != 'ex mined':
                        self._log['behavior_prp'] = 'ex mined'
                elif blocks.index == 0:
                    print(f'adver get TX{blocks.name}')
                else:
                    # pass
                    ds_strategy = global_var.get_double_spending_strategy()
                    if ds_strategy == 1:
                        if (blocks.index - 2) in self._log['success_vtchain_index']:
                            attack_block_vt = blocks
                            self._fork_block[attack_block_vt.index - 2] = attack_block_vt
                            print('in upload')
                            self.behavior.upload(network=self.network,
                                                 adver_chain_prp=self.adver_chain_prp,
                                                 adver_chain_vt=self.adver_chain_vt,
                                                 current_miner=current_miner,
                                                 round=round,
                                                 miner_list=self.adver_list,
                                                 fork_block=[self._fork_block[attack_block_vt.index - 2]]
                                                 )
                    for miner in self.adver_list:
                        if miner.miner_id != blocks.blockhead.miner:
                            local_chain_vt = miner.consensus.local_chain_vt[blocks.index - 2]
                            votes_on_prp_bks = miner.consensus.votesOnPrpBks[blocks.index - 2]

                            for prp_block in blocks.vtonprp:  # assuming blocks.vtonprp contains the necessary blocks
                                print(f'miner {miner.miner_id} get block{blocks.name} vt on {prp_block.name}')
                                vtc = local_chain_vt
                                if vtc.has_voted(prp_block.height):
                                    old_block_name = vtc.votes[prp_block.height]
                                    print(f'old name is {old_block_name}')
                                    if old_block_name in votes_on_prp_bks:
                                        votes_on_prp_bks.remove(old_block_name)
                                    vtc.votes[prp_block.height] = prp_block
                                else:
                                    # 如果之前没有对该高度进行过投票，则直接记录新的投票
                                    vtc.vote(prp_block.height, prp_block)

            #################################################################
            #记录诚实者提议者链确认高度
            #通过诚实者提议者链确认高度来判断同级别的诚实提议者块是否被确认
            prp_height_confirmed = global_var.get_cfheight()
            self._log['fail_num'] = 0
            self._log['fail_vtchain_index'] = []
            ds_strategy = global_var.get_double_spending_strategy()
            if ds_strategy == 2:
                self._log['success_vtchain_index'] = []
            for i in range(global_var.get_vtnum()):
                honest_height = honest_heights_vt[i]
                adver_height = adver_heights_vt[i]
                # print(f'in vt chain{i} honest height {honest_height} and adver height {adver_height} and prp_height_confirmed:{prp_height_confirmed} self.attack_block.height {self.attack_block.height}')

                if not prp_height_confirmed or self.attack_block.height > max(prp_height_confirmed):
                    pass
                    # file_path = f'D:/double-spending_count.txt'  # 请将 'your_file_path_here.txt' 替换为你指定的文件路径
                    # with open(file_path, 'a') as f:
                    #     f.write(f"not confirmed in round {round}\n")
                    # self._log['behavior'][i] = 'conforming ' + str(prp_height_confirmed) + '/' + str(self.attack_block.height)
                else:
                    print(f'in vtchain {i} honest_height {honest_height} and adver_height {adver_height}')
                    if honest_height - adver_height >= ng:
                        # 攻击链比诚实链落后Ng个区块
                        if i not in self._log['success_vtchain_index']:
                            self._log['fail_num'] += 1
                            if i not in self._log['fail_vtchain_index']:
                                self._log['fail_vtchain_index'].append(i)
                        #####################################################################################
                        # self._fork_block[i] = bh.adopt(adver_chain=self.adver_chain_vt[i],
                        #                             honest_chain=self.honest_chain_vt[i])
                        # self._fork_height[i] = self._fork_block[i].get_height()
                        # if self._log['behavior'][i] != 'adopt':
                        #     self._log['fail'] += 1
                        # self._log['behavior'][i] = 'adopt'
                    # elif adver_height >= honest_height and honest_height > 0 and adver_height > 0:
                    elif adver_height >= honest_height:
                        # 攻击链比诚实链长（且双方高度都不为0，排除只有创世块的情况）
                        if i not in self._log['success_vtchain_index']:
                            self._log['success_vtchain_index'].append(i)
                        ds_strategy = global_var.get_double_spending_strategy()
                        if ds_strategy == 1:
                            if not self.upload_prp:
                                blocks = bh.upload(network=self.network,
                                                   adver_chain_prp=self.adver_chain_prp,
                                                   adver_chain_vt=self.adver_chain_vt,
                                                   current_miner=current_miner,
                                                   round=round,
                                                   miner_list=self.adver_list,
                                                   fork_block=[self.attack_block] if self.attack_block is not None else
                                                   [self.honest_chain_prp.head])
                                self.upload_prp = True
                            blocks = bh.upload_ds(network=self.network,
                                                  adver_chain_prp=self.adver_chain_prp,
                                                  adver_chain_vt=self.adver_chain_vt,
                                                  current_miner=current_miner,
                                                  round=round,
                                                  miner_list=self.adver_list,
                                                  fork_block=[self._fork_block[i]] if self._fork_block[
                                                                                          i] is not None else [
                                                      self.honest_chain_vt[i].head],
                                                  index=i + 2,
                                                  global_chain_prp=self.global_chain_prp,
                                                  global_chain_vt=self.global_chain_vt)
                            self._lastattackblock[i] = self.adver_chain_vt[i].get_last_block()
                            print(f'now adver_chain_vt{i} has last block: {self._lastattackblock[i]}')
                            if self._log['behavior'][i] != 'override':
                                self._attack_success_detect = True
                            self._log['behavior'][i] = 'override'
                        #####################################################################################
                    elif adver_height == (honest_height - 1):
                        # 攻击链与诚实链 matching
                        self._log['behavior'][i] = 'matching'
            print('now success chain:', self._log['success_vtchain_index'])
            print('now fail chain:', self._log['fail_vtchain_index'])

            if self._log['fail_num'] > global_var.get_vote_threshold() or (len(self._log['success_vtchain_index']) + self._log['fail_num'] == global_var.get_vtnum() and len(self._log['success_vtchain_index']) < global_var.get_vote_threshold()):
                print('double-spending fail!')
                # file_path = f'D:/double-spending_count.txt'  # 请将 'your_file_path_here.txt' 替换为你指定的文件路径
                # with open(file_path, 'a') as f:
                #     f.write(f"attack fail in {self._log['fail_vtchain_index']} and success in {self._log['success_vtchain_index']}\n")
                num = global_var.get_threshold_num()
                if num in self._log['success_vtchain_index']:
                    global_var.set_threshold_chain_flag(-1)
                global_var.set_onetime_double_spending(False)
                for miner in self.adver_list:
                    for i in range(global_var.get_vtnum()):
                        voteon = miner.consensus.votesOnPrpBks[i]
                        if self.attack_block in voteon:
                            voteon.remove(self.attack_block)
                            miner.consensus.votesOnPrpBks[i] = voteon
                self.attack_flag = False
                global_var.set_attack_flag_ds(False)
                fork_block = self.behavior.adopt(adver_chain=self.adver_chain_prp, honest_chain=self.honest_chain_prp)
                for i in range(global_var.get_vtnum()):
                    self._fork_block[i], vtonprps = bh.adopt_fail_after_doublespending(adver_chain=self.adver_chain_vt[i],
                                                honest_chain=self.honest_chain_vt[i])
                    for miner in self.adver_list:
                        for prp_block in vtonprps:
                            if miner.consensus.in_local_chain_prp(prp_block):
                                vtc = miner.consensus.local_chain_vt[i]
                                if vtc.has_voted(prp_block.height):
                                    old_block_name = vtc.votes[prp_block.height]
                                    voteon = miner.consensus.votesOnPrpBks[i]
                                    if old_block_name in voteon:
                                        voteon.remove(old_block_name)
                                        vtc.votes[prp_block.height] = prp_block
                                else:
                                    # 如果之前没有对该高度进行过投票，则直接记录新的投票
                                    vtc.vote(prp_block.height, prp_block)
                        print(f'miner {miner.miner_id} now change votes to')
                        print(miner.consensus.votesOnPrpBks)
                    self._fork_height[i] = self._fork_block[i].get_height()
                    if self._log['behavior'][i] != 'adopt':
                        self._log['fail'] += 1
                    self._log['behavior'][i] = 'adopt'
                self._log['fail_num'] = 0
                self._log['success_vtchain_index'] = []
            elif len(self._log['success_vtchain_index']) >= global_var.get_vote_threshold():
                print('double-spending success!')
                num = global_var.get_threshold_num()
                if num in self._log['success_vtchain_index']:
                    global_var.set_threshold_chain_flag(1)
                global_var.set_onetime_double_spending(False)
                self.upload_prp = False
                global_var.add_ds_success_times()
                # file_path = f'D:/double-spending_count.txt'  # 请将 'your_file_path_here.txt' 替换为你指定的文件路径
                # with open(file_path, 'a') as f:
                #     f.write(f"attack success in {self._log['success_vtchain_index']}\n")
                global_var.set_attack_flag_ds(False)
                self.attack_flag = False
                ds_strategy = global_var.get_double_spending_strategy()
                if ds_strategy == 2:
                    blocks = bh.upload(network=self.network,
                                       adver_chain_prp=self.adver_chain_prp,
                                       adver_chain_vt=self.adver_chain_vt,
                                       current_miner=current_miner,
                                       round=round,
                                       miner_list=self.adver_list,
                                       fork_block=[self.attack_block] if self.attack_block is not None else
                                       [self.honest_chain_prp.head])
                for i in range(global_var.get_vtnum()):
                    ds_strategy = global_var.get_double_spending_strategy()
                    if ds_strategy == 2:
                        if i in self._log['success_vtchain_index']:
                            blocks = bh.upload_ds(network=self.network,
                                               adver_chain_prp=self.adver_chain_prp,
                                               adver_chain_vt=self.adver_chain_vt,
                                               current_miner=current_miner,
                                               round=round,
                                               miner_list=self.adver_list,
                                               fork_block=[self._fork_block[i]] if self._fork_block[i] is not None else [
                                                   self.honest_chain_vt[i].head],
                                               index=i+2,
                                               global_chain_prp = self.global_chain_prp,
                                               global_chain_vt = self.global_chain_vt)
                            self._lastattackblock[i] = self.adver_chain_vt[i].get_last_block()
                            print(f'now adver_chain_vt{i} has last block: {self._lastattackblock[i]}')
                            if self._log['behavior'][i] != 'override':
                                self._attack_success_detect = True
                            self._log['behavior'][i] = 'override'
                        else:
                            self._fork_block[i] = bh.adopt(adver_chain=self.adver_chain_vt[i],
                                                           honest_chain=self.honest_chain_vt[i])
                            self._fork_height[i] = self._fork_block[i].get_height()
                            if self._log['behavior'][i] != 'adopt':
                                self._log['behavior'][i] = 'adopt'
                    elif ds_strategy == 1:
                        if i not in self._log['success_vtchain_index']:
                            self._fork_block[i] = bh.adopt(adver_chain=self.adver_chain_vt[i],
                                                           honest_chain=self.honest_chain_vt[i])
                            self._fork_height[i] = self._fork_block[i].get_height()
                            if self._log['behavior'][i] != 'adopt':
                                self._log['behavior'][i] = 'adopt'
                self._log['success_vtchain_index'] = []
            # self._log['success_vtchain_index'] = []

    def clear_record_stage(self, round):
        bh = self.behavior
        # self._log['honest_chain'] = self.honest_chain.last_block.name,self.honest_chain.last_block.height
        # self._log['adver_chain'] = self.adver_chain.last_block.name,self.adver_chain.last_block.height
        # self._log['fork_block'] = self._fork_block.name  if self._fork_block != None else self.honest_chain.head.name
        # self._log['attacked_block'] = self._lastattackblock.name if self._lastattackblock != None else None
        # self.__log['other']=self.__log['other']+' fork block is '+self.__fork_blockname
        bh.clear(miner_list = self.adver_list)# 清空
        # self.resultlog2txt(round)

    def excute_this_attack_per_round(self, round):
        '''双花攻击'''
        ## 1. renew stage
        newest_block, mine_input= self.renew_stage(round)
        ## 2. attack stage
        self.attack_stage(round, mine_input)
        ## 3. clear and record stage
        self.clear_record_stage(round)
        return self.attack_flag


    def info_getter(self):

        rate, thr_rate = self.__success_rate()
        return {'Success Rate': '{:.4f}'.format(rate),
                'Theory rate in SynchronousNetwork': '{:.4f}'.format(thr_rate),
                'Attack times': self._log['success']+self._log['fail'],
                'Success times': self._log['success'],
                'Ng': self.attack_arg['Ng'],
                'N': self.attack_arg['N']
                }

    def __success_rate(self):
        if self._log['success'] != 0 or self._log['fail'] != 0:
            rate = self._log['success']/(self._log['success']+self._log['fail'])
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
            return -1,-1

    def resultlog2txt(self,round):
        if self._simplifylog != self._log:
            self._simplifylog = copy.deepcopy(self._log)
            ATTACK_RESULT_PATH = global_var.get_attack_result_path()
            with open(ATTACK_RESULT_PATH / f'Attack Log.txt','a') as f:
                print(self._log,round, '\n',file=f)


