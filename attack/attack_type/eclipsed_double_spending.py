'''
定义honestminging攻击
'''
import math
import random

import attack.attack_type as aa
import global_var
from data import Message
from collections import defaultdict
import copy


class EclipsedDoubleSpending(aa.AttackType):
    '''
    算力攻击
    '''
    def __init__(self) -> None:
        super().__init__()
        self._log = {
            'honest_chain': None,
            'adver_chain': None,
            'eclipse_miner_block': None,
            'eclipse_block': None,
            'eclipse_from': None,
            'fork_block':None,
            'success': 0,
            'fail':0,
            'behavior':None,
            
        }
        self._simplifylog = {}
        self._fork_block: Message = None
        self._fork_height:int = 0
        self._attackblock = defaultdict(Message)
        self._lastattackblock: Message = None # 用于记录上传的最新的attackblock
        self._attack_success_detect: bool = False
        self._eclipse_block: Message = None # 记录 eclipse对象的newestblock状况
        self._eclipse_block_from: Message = None # 记录 eclipse最新区块的来源
        self._syn_blocks: dict = {} # 记录 已向邻居同步过的区块
        self._incoming_eclipse_block = []

    
    def renew_stage(self, round):
        ## 1. renew stage
        bh = self.behavior
        newest_block, mine_input, imcoming_block_from_eclipse = bh.renew(adver_list = self.adver_list,
                                 honest_chain = self.honest_chain,round = round,eclipse_list_ids=self.eclipsed_list_ids)
        
        # renew eclipse part
        # 获取eclipse的最新状态
        # 找到eclipse中最长的链 并判断它的来源
        self._eclipse_block = self._eclipse_block if self._eclipse_block!= None else self.honest_chain.head
        newest_block_from_eclipse = self._eclipse_block
        eclipse_update = False
        self._incoming_eclipse_block = []
        if len(imcoming_block_from_eclipse) >0:
            for hash,block in imcoming_block_from_eclipse.items():
                    self._incoming_eclipse_block.append(block.name)
                    if block.get_height() > newest_block_from_eclipse.get_height():
                        # 说明存在比adver掌握的eclipse最新状态 更新的状态
                        eclipse_update = True
                        newest_block_from_eclipse = block
        # self._eclipse_block = newest_block_from_eclipse
        if eclipse_update:
            self._eclipse_block = newest_block_from_eclipse
            # 说明 存在eclipse更新 需要判断这个最新区块来源于哪里
            # 1. 更新自adver
            #   fork-h-h-h
            #      |-a-a-e <- 
            # 2. 更新自fork
            #   fork-h-h-h
            #      |-e-e-e <-          
            # 3. 更新自honest
            #   fork-h-h-h-e <-
            #      |-a-a-a-a
            from_block = newest_block_from_eclipse
            self._fork_block = self._fork_block if self._fork_block != None else self.adver_chain.head
            while(from_block != None):
                if from_block.blockhash == self._fork_block.blockhash:
                    break
                if from_block.isAdversaryBlock:
                    break
                if not from_block.isAdversaryBlock and from_block.blockhead.miner not in self.eclipsed_list_ids:
                    break
                temp_block = self.adver_chain.search_block_by_hash(from_block.blockhead.prehash)
                if from_block.parentblock == None:
                    from_block.parentblock = temp_block
                from_block = temp_block
            from_block = from_block if from_block != None else self.adver_chain.head
            self._eclipse_block_from = from_block
        else:
            # 不存在 eclipse 更新 则 最新eclipse区块来源不变
            self._eclipse_block_from = self._eclipse_block_from if self._eclipse_block_from != None else self.adver_chain.head
        

        # detect newestblock is adver or not
        if self._attack_success_detect and self.honest_chain.search_block(self._lastattackblock):
            self._log['success'] = self._log['success'] + 1
            self._attack_success_detect = False
            self._fork_block = self._lastattackblock
            self._fork_height = self._fork_block.get_height()
        return newest_block, mine_input
    

    def attack_stage(self, round, mine_input):
        mine_input = self.behavior.ATTACKER_INPUT or mine_input
        bh = self.behavior
        n = self.attack_arg['N']
        ng = self.attack_arg['Ng']
        current_miner = random.choice(self.adver_list)


        # 根据 最新eclipse区块的来源判断 是否更新adver
        eclipse_height = self._eclipse_block.get_height()
        adver_height = self.adver_chain.get_height()
        if eclipse_height > adver_height:
            # 如果eclipse_height 高于 adver_height adver 需要对来源进行判断
            if self._eclipse_block_from.isAdversaryBlock:
                # 来源于adver 执行adopt
                # 这里用add block 替代 
                self.adver_chain.add_block_forcibly(self._eclipse_block)
            elif self._eclipse_block_from.blockhash == self._fork_block.blockhash:
                # 来源于 fork 接受之 操作同上
                self.adver_chain.add_block_forcibly(self._eclipse_block)
            else:
                # 来源于 honest 放任之
                pass
        elif eclipse_height < adver_height:

            # adver_height 高于 eclipse_height 强行将adver状态更新给ec
            sync_block = self.adver_chain.get_last_block()
            if sync_block.blockhash not in self._syn_blocks:
                self._syn_blocks[sync_block.blockhash] = sync_block
                blocks = bh.upload(adver_chain = self.adver_chain,
                                    current_miner = current_miner, 
                                    round = round,
                                    adver_list = self.adver_list,
                                    fork_block= self._eclipse_block if self._eclipse_block != None else self.honest_chain.head,
                                    strategy = "SPEC_TARGETS", forward_target = self.eclipsed_list_ids, syncLocalChain = True)
            # 因为 ec_miner 更新过了所以要将 eclipse_block 更新为 adver
            self._eclipse_block = self.adver_chain.get_last_block()
            self._eclipse_block_from = self._eclipse_block
        elif eclipse_height == adver_height:
            # 等高 那 不需要进行任何操作
            pass

        '''
        与ec交换初期情报之后 则A==E 即 现在E肯定与A同步
        '''
        # 更新 诚实链 和 攻击链 的高度
        # 诚实链 可能存在更新
        honest_height = self.honest_chain.last_block.get_height()
        adver_height = self.adver_chain.last_block.get_height() 
        

        if honest_height - self._fork_height < n:
            # 诚实链 自分叉之后 分叉起点块还没有达到确认数
            # adver 正常挖 
            # 若挖出需要与ec同步 然后结束本回合
            attack_mine,blocks = bh.mine(adver_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain,
                                         consensus = self.adver_consensus,
                                         round = round)
            ### add_forcibly 替代 spec_target
            if attack_mine:

                # 还处于确认当中 如果 adver 挖出来了 将区块共享给 ec
                sync_block = self.adver_chain.get_last_block()
                if sync_block.blockhash not in self._syn_blocks:
                    self._syn_blocks[sync_block.blockhash] = sync_block
                    blocks = bh.upload(adver_chain = self.adver_chain,
                                        current_miner = current_miner, 
                                        round = round,
                                        adver_list = self.adver_list,
                                        fork_block= self._eclipse_block if self._eclipse_block != None else self.honest_chain.head,
                                        strategy = "SPEC_TARGETS", forward_target = self.eclipsed_list_ids, syncLocalChain = True)
                # 因为 ec_miner 更新过了所以要将 eclipse_block 更新为 adver
                self._eclipse_block = self.adver_chain.get_last_block()
                self._eclipse_block_from = self._eclipse_block

            self._log['behavior'] = 'conforming ' + str(honest_height - self._fork_height) + '/' +str(n)
        elif honest_height - self._fork_height >= n:
            # 从分叉起点开始 确认数以足够
            if honest_height - adver_height >= ng:
            # 攻击链比诚实链落后Ng个区块
                self._fork_block = bh.adopt(adver_chain = self.adver_chain, honest_chain = self.honest_chain)
                self._fork_height = self._fork_block.get_height()
                attack_mine,blocks = bh.mine(adver_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain, 
                                         consensus = self.adver_consensus,
                                         round = round) 

                ### 与普通DB不同 adver 在同步之后 还要同步给 ec
                sync_block = self.adver_chain.get_last_block()
                if sync_block.blockhash not in self._syn_blocks:
                    self._syn_blocks[sync_block.blockhash] = sync_block
                    blocks = bh.upload(adver_chain = self.adver_chain,
                                        current_miner = current_miner, 
                                        round = round,
                                        adver_list = self.adver_list,
                                        fork_block= self._eclipse_block if self._eclipse_block != None else self.honest_chain.head,
                                        strategy = "SPEC_TARGETS", forward_target = self.eclipsed_list_ids, syncLocalChain = True)
                ### 同时更新掌握的eclipse状态
                # 因为 adver 可能 mine 成功 因此用adver最末链更新状态
                self._eclipse_block = self.adver_chain.get_last_block()
                self._eclipse_block_from = self._eclipse_block

                if self._log['behavior'] != 'adopt':
                    self._log['fail'] = self._log['fail'] + 1
                self._log['behavior'] = 'adopt'
            elif adver_height > honest_height:
                # 攻击链比诚实链长
                # 然后开挖
                attack_mine,blocks = bh.mine(adver_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain, 
                                         consensus = self.adver_consensus,
                                         round = round)

                blocks = bh.upload(adver_chain = self.adver_chain,
                                 current_miner = current_miner, 
                                 round = round,
                                 adver_list = self.adver_list,
                                 fork_block= self._fork_block if self._fork_block != None else self.honest_chain.head)
                self._lastattackblock = self.adver_chain.get_last_block()


                # 这里还是对ec全面同步 防止upload未成功传递至ec_miner
                sync_block = self.adver_chain.get_last_block()
                if sync_block.blockhash not in self._syn_blocks:
                    self._syn_blocks[sync_block.blockhash] = sync_block
                    blocks = bh.upload(adver_chain = self.adver_chain,
                                        current_miner = current_miner, 
                                        round = round,
                                        adver_list = self.adver_list,
                                        fork_block= self._eclipse_block if self._eclipse_block != None else self.honest_chain.head,
                                        strategy = "SPEC_TARGETS", forward_target = self.eclipsed_list_ids, syncLocalChain = True)
                self._eclipse_block = self._lastattackblock
                self._eclipse_block_from = self._eclipse_block
                
                if self._log['behavior'] != 'override':
                    self._attack_success_detect = True

                self._log['behavior'] = 'override'
            elif adver_height == honest_height:
                # adver 处于 攻击姿态 但是 与 honest 等长
                # 开挖
                attack_mine,blocks = bh.mine(adver_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain, 
                                         consensus = self.adver_consensus,
                                         round = round)
                if attack_mine:
                    # 如果挖出来 且等长 则立刻发布
                    # 这意味着 攻击链比 诚实链 长了
                    blocks = bh.upload(adver_chain = self.adver_chain,
                                 current_miner = current_miner, 
                                 round = round,
                                 adver_list = self.adver_list,
                                 fork_block= self._fork_block if self._fork_block != None else self.honest_chain.head)
                    self._lastattackblock = self.adver_chain.get_last_block()


                    if self._log['behavior'] != 'override':
                        self._attack_success_detect = True
                    self._log['behavior'] = 'override'
                else:
                    self._log['behavior'] = 'matching'

                # 这里还是对ec全面同步 防止upload未成功传递至ec_miner
                sync_block = self.adver_chain.get_last_block()
                if sync_block.blockhash not in self._syn_blocks:
                    self._syn_blocks[sync_block.blockhash] = sync_block
                    blocks = bh.upload(adver_chain = self.adver_chain,
                                        current_miner = current_miner, 
                                        round = round,
                                        adver_list = self.adver_list,
                                        fork_block= self._eclipse_block if self._eclipse_block != None else self.honest_chain.head,
                                        strategy = "SPEC_TARGETS", forward_target = self.eclipsed_list_ids, syncLocalChain = True)
                self._eclipse_block = self._lastattackblock
                self._eclipse_block_from = self._eclipse_block

            else:
                # 攻击链与诚实链 matching
                # 开挖
                attack_mine,blocks = bh.mine(adver_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain,
                                         consensus = self.adver_consensus,
                                         round = round)
                if attack_mine:
                    # 如果挖出来了要同步给 ec
                    sync_block = self.adver_chain.get_last_block()
                    if sync_block.blockhash not in self._syn_blocks:
                        self._syn_blocks[sync_block.blockhash] = sync_block
                        blocks = bh.upload(adver_chain = self.adver_chain,
                                            current_miner = current_miner, 
                                            round = round,
                                            adver_list = self.adver_list,
                                            fork_block= self._eclipse_block if self._eclipse_block != None else self.honest_chain.head,
                                            strategy = "SPEC_TARGETS", forward_target = self.eclipsed_list_ids, syncLocalChain = True)
                    self._eclipse_block = self.adver_chain.get_last_block()
                    self._eclipse_block_from = self._eclipse_block

                self._log['behavior'] = 'matching'

        self._log['eclipse_block'] = self._eclipse_block.name if self._eclipse_block != None else None
        self._log['eclipse_from'] = self._eclipse_block_from.name if self._eclipse_block_from != None else None

    def clear_record_stage(self, round):
        bh = self.behavior
        self._log['honest_chain']=self.honest_chain.last_block.name,self.honest_chain.last_block.height
        self._log['adver_chain']=self.adver_chain.last_block.name,self.adver_chain.last_block.height
        self._log['fork_block']=self._fork_block.name  if self._fork_block != None else self.honest_chain.head.name
        self._log['attacked_block'] = self._lastattackblock.name if self._lastattackblock != None else None
        self._log['_incoming_eclipse_block'] = self._incoming_eclipse_block
        bh.clear(adver_list = self.adver_list)# 清空
        self.resultlog2txt(round)
        
    def excute_this_attack_per_round(self, round):
        '''双花攻击'''
        ## 1. renew stage
        newest_block, mine_input= self.renew_stage(round)
        ## 2. attack stage
        self.attack_stage(round, mine_input)
        ## 3. clear and record stage
        self.clear_record_stage(round)

        
    def info_getter(self, miner_num):

        success_times_list =[]
        for adver_miner in self.adver_list:
            last_block = adver_miner.consensus.local_chain.get_last_block()
            temp_times = 0
            while last_block:
                if len(last_block.next)>1:
                    for block in last_block.next:
                        if block.blockhead.miner in self.adver_list_ids or self.eclipsed_list_ids:
                            temp_times += 1
                            break
                last_block = last_block.parentblock
            success_times_list.append(temp_times)
        success_times_list.sort()
        success_times = success_times_list[-1]
        rate, thr_rate = self.__success_rate(miner_num)
        return {'Success Rate': '{:.4f}'.format(success_times/(self._log['success']+self._log['fail'])),
                'Theory rate in SynchronousNetwork (consider eclipsed miners)': '{:.4f}'.format(thr_rate),
                'Attack times': self._log['success']+self._log['fail'],
                'Success times': success_times,
                'eclipsed ids': len(self.eclipsed_list_ids),
                'Ng': self.attack_arg['Ng'],
                'N': self.attack_arg['N'],
                }
        return None
    

    def __judge_block_from(self,block:Message) -> Message:
        while block!=None and block.blockhead.miner in self.eclipsed_list_ids :
            block = block.parentblock
            if block.blockhead.miner in self.adver_list_ids:
                break
        return block
    
    def __judge_block_adver_valid(self,block:Message,fork_block:Message) -> bool:
        while block!=None and block.blockhash != fork_block.blockhash:
            if block.isAdversaryBlock:
                return True
            block = block.parentblock
        return False


    def __success_rate(self,miner_num):
        if self._log['success'] != 0 or self._log['fail'] != 0:
            rate = self._log['success']/(self._log['success']+self._log['fail'])
            ## 计算理论成功率
            tmp = 0
            n = self.attack_arg['N']
            ng = self.attack_arg['Ng']
            beta = len(self.adver_list)/(miner_num-len(self.adver_list))
            beta = (len(self.adver_list)+len(self.eclipsed_list_ids))/(miner_num-len(self.adver_list)-len(self.eclipsed_list_ids))
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


