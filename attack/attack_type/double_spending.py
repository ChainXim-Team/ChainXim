'''
定义honestminging攻击
'''
import math
import random
from typing import Optional

import attack.attack_type as aa
import global_var
from data import Block
from collections import defaultdict
import copy


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
            'fail':0,
            'behavior':None,
            'fork_block':None
        }
        self._simplifylog = {}
        self._fork_block: Block = None
        self._fork_height:int = 0
        self._attackblock = defaultdict(Block)
        self._lastattackblock: Block = None # 用于记录上传的最新的attackblock
        self._attack_success_detect: bool = False
        self.attackers_with_honest_neighbors:Optional[dict] = None # 记录每个攻击者的转发对象，记录至少有一个诚实邻居的攻击者列表
        # Pre-mining is an optional preparation phase for double spending.
        # It deliberately has a different base block from the block that is
        # eventually attacked (self._fork_block).
        self._premining_enabled = False
        self._premining_end_condition = 'height'
        self._premining_target_height = None
        self._premining_target_round = None
        self._premining_start_height = None
        self._premining_started = False
        self._premining_base_block: Block = None
        self._premining_end_tip_hash = None
        self._premining_end_height = None
        self._premining_end_round = None
        self._premining_end_lead = None
        self._premining_max_lead = 0
        self._phase = 'DOUBLE_SPENDING'

    def set_init(self, honest_chain, adver_list, adver_consensus, attack_arg,
                 eclipsed_list_ids=None):
        super().set_init(honest_chain=honest_chain,
                         adver_list=adver_list,
                         adver_consensus=adver_consensus,
                         attack_arg=attack_arg,
                         eclipsed_list_ids=eclipsed_list_ids)
        attack_arg = attack_arg or {}
        self._premining_enabled = bool(attack_arg.get('premining_enabled', False))
        self._premining_end_condition = str(
            attack_arg.get('premining_end_condition', 'height')
        ).lower()
        if self._premining_end_condition not in ('height', 'round'):
            raise ValueError("premining_end_condition must be 'height' or 'round'")
        self._premining_start_height = int(
            attack_arg.get('premining_start_height', global_var.get_attack_initial_height())
        )
        self._premining_target_height = attack_arg.get('premining_target_height')
        self._premining_target_round = attack_arg.get('premining_target_round')
        if self._premining_target_height is not None:
            self._premining_target_height = int(self._premining_target_height)
        if self._premining_target_round is not None:
            self._premining_target_round = int(self._premining_target_round)
        if self._premining_enabled:
            if self._premining_end_condition == 'height':
                if self._premining_target_height is None:
                    raise ValueError('premining_target_height is required for height mode')
                if self._premining_target_height < self._premining_start_height:
                    raise ValueError('premining_target_height must be >= premining_start_height')
            elif self._premining_target_round is None:
                raise ValueError('premining_target_round is required for round mode')
            self._phase = 'PREMINING'

    def should_publish_adver_chain(self):
        """Whether Adversary may mirror the private chain into global_chain."""
        return self._phase == 'DOUBLE_SPENDING'

    @staticmethod
    def _block_at_height(tip, height):
        cur = tip
        while cur is not None and cur.get_height() > height:
            cur = cur.parentblock
        return cur if cur is not None and cur.get_height() == height else None

    def _first_block_after_premining_end(self):
        """Find the first honest block produced after the end round.

        The attacker may execute before honest miners in the round in which
        round-mode pre-mining ends. Blocks stamped with that same round still
        belong to the pre-mining boundary; the first block with a later round
        is the DoubleSpending target.
        """
        if self._premining_end_tip_hash is None:
            return None
        path = []
        cur = self.honest_chain.get_last_block()
        while cur is not None and cur.blockhash != self._premining_end_tip_hash:
            path.append(cur)
            cur = cur.parentblock
        if cur is None or not path:
            return None
        for candidate in reversed(path):
            timestamp = getattr(candidate.blockhead, 'timestamp', None)
            if (self._premining_end_round is None
                    or timestamp is None
                    or timestamp > self._premining_end_round):
                return candidate
        # All newly observed blocks were produced in the ending round. They
        # form the boundary tip, not the target, so advance the snapshot.
        newest = path[0]
        self._premining_end_tip_hash = newest.blockhash
        self._premining_end_height = newest.get_height()
        return None

    def _start_premining_if_ready(self, honest_height):
        if self._premining_started or honest_height < self._premining_start_height:
            return False
        # This is only the private-chain base. It is never used as the
        # double-spending target or for confirmation counting.
        self._premining_base_block = self.behavior.adopt(
            adver_chain=self.adver_chain,
            honest_chain=self.honest_chain
        )
        self._premining_started = True
        return True

    def _finish_premining_by_height(self):
        target = self._block_at_height(
            self.honest_chain.get_last_block(), self._premining_target_height
        )
        if target is None:
            return False
        # In height mode, the block reaching the configured height is the
        # block being double-spent (e.g. H10, not H11).
        self._fork_block = target
        self._fork_height = target.get_height()
        self._phase = 'DOUBLE_SPENDING'
        self._premining_end_tip_hash = target.blockhash
        self._premining_end_height = target.get_height()
        # Capture the lead exactly at the PREMINING -> DOUBLE_SPENDING
        # transition, before any normal double-spending mining in this round.
        self._premining_end_lead = (
            self.adver_chain.get_height() - self.honest_chain.get_height()
        )
        return True

    def _finish_premining_by_round(self, round):
        # Round mode ends at the current honest tip. The attacker immediately
        # keeps mining, while the first honest block after this tip becomes
        # the double-spending target.
        self._premining_end_tip_hash = self.honest_chain.get_last_block().blockhash
        self._premining_end_height = self.honest_chain.get_height()
        self._premining_end_round = round
        self._premining_end_lead = (
            self.adver_chain.get_height() - self.honest_chain.get_height()
        )
        self._phase = 'DOUBLE_SPENDING_PENDING_TARGET'
        return True

    def _update_premining_lead(self):
        lead = self.adver_chain.get_height() - self.honest_chain.get_height()
        self._premining_max_lead = max(self._premining_max_lead, lead)

    def _execute_private_mining(self, round, mine_input, current_miner):
        self.behavior.mine(adver_list=self.adver_list,
                           current_miner=current_miner,
                           miner_input=mine_input,
                           adver_chain=self.adver_chain,
                           consensus=self.adver_consensus,
                           round=round)
        self._update_premining_lead()
    
    def renew_stage(self, round):
        ## 1. renew stage
        if self.adver_list[0].network_has_topology:
            self.attackers_with_honest_neighbors = {}
            for attacker in self.adver_list:
                forwarding_targets = [neighbor_id for neighbor_id in attacker.neighbors if neighbor_id not in self.adver_list_ids]
                if len(forwarding_targets) > 0:
                    self.attackers_with_honest_neighbors[attacker] = forwarding_targets
        bh = self.behavior
        newest_block, mine_input = bh.renew(adver_list = self.adver_list,
                                 honest_chain = self.honest_chain,round = round,
                                 attackers_with_honest_neighbors=self.attackers_with_honest_neighbors)

        if self._attack_success_detect and (not self.adver_list[0].network_has_topology \
                                             or self.honest_chain.search_block(self._lastattackblock)):
            self._log['success'] = self._log['success'] + 1
            self._attack_success_detect = False
            self._fork_block = self._lastattackblock
            self._fork_height = self._fork_block.get_height()
        return newest_block, mine_input
    
    ATTACK_INITIAL_HEIGHT = 3 # 攻击开始的高度

    def attack_stage(self, round, mine_input):
        mine_input = self.behavior.ATTACKER_INPUT or mine_input
        bh = self.behavior
        n = self.attack_arg['N']
        ng = self.attack_arg['Ng']

        # 如果找到了合适的攻击者，随机选一个；
        if self.attackers_with_honest_neighbors:
            current_miners = list(self.attackers_with_honest_neighbors.keys()) # the initiators for the upload operation
            current_miner = random.choice(current_miners) # the miner that mines new blocks
        else:
            current_miners = random.sample(self.adver_list, 1)
            current_miner = current_miners[0]

        honest_height = self.honest_chain.last_block.get_height()
        if self._premining_enabled:
            # Before the configured start height the attacker does not mine.
            if honest_height < self._premining_start_height:
                return

            self._start_premining_if_ready(honest_height)

            if self._phase == 'PREMINING':
                # At the beginning of every pre-mining round, the attacker adopts the honest chain whenever its private chain
                # is behind.  The end-condition check and private mining must use the post-adoption height.
                adver_height = self.adver_chain.last_block.get_height()
                if adver_height < honest_height:
                    self.behavior.adopt(
                        adver_chain=self.adver_chain,
                        honest_chain=self.honest_chain
                    )
                    adver_height = self.adver_chain.last_block.get_height()

                if self._premining_end_condition == 'height':
                    if honest_height >= self._premining_target_height:
                        self._finish_premining_by_height()
                    else:
                        self._execute_private_mining(round, mine_input, current_miner)
                        return
                elif round >= self._premining_target_round:
                    self._finish_premining_by_round(round)
                else:
                    self._execute_private_mining(round, mine_input, current_miner)
                    return

                # In round mode this phase transition happens immediately at
                # the target round. The attacker still mines in this call;
                # it never idles while waiting for the first honest target.
                if self._phase == 'DOUBLE_SPENDING_PENDING_TARGET':
                    self._execute_private_mining(round, mine_input, current_miner)
                    return

            if self._phase == 'DOUBLE_SPENDING_PENDING_TARGET':
                target = self._first_block_after_premining_end()
                if target is not None:
                    self._fork_block = target
                    self._fork_height = target.get_height()
                    self._phase = 'DOUBLE_SPENDING'
                else:
                    self._execute_private_mining(round, mine_input, current_miner)
                    return

        elif honest_height < global_var.get_attack_initial_height():
            # 进行诚实挖矿，期间不计算攻击成功或者失败   # 为了确保攻击者能比诚实矿工抢先delta获得区块，攻击者在攻击初期不进行攻击，确保攻击开始时的区块来自诚实矿工
            # if self.honest_chain.get_height() > self.adver_chain.get_height():       
            #     self.behavior.adopt(adver_chain = self.adver_chain, honest_chain = self.honest_chain)
            # attack_mine,block = self.behavior.mine(adver_list = self.adver_list,
            #                                 current_miner = current_miner,
            #                                 miner_input = mine_input,
            #                                 adver_chain = self.adver_chain,
            #                                 consensus = self.adver_consensus,
            #                                 round = round)
            # if attack_mine:
            #     self.behavior.upload(adver_chain = self.adver_chain,
            #                         current_miners = current_miners,
            #                         round = round,
            #                         adver_list = self.adver_list,
            #                         fork_block = self.honest_chain.get_last_block(),
            #                         syncLocalChain = False)
            return
        elif self._fork_block is None:
            self._fork_block = self.behavior.adopt(adver_chain = self.adver_chain, honest_chain = self.honest_chain)
            self._fork_height = self._fork_block.get_height()
        
        adver_height = self.adver_chain.last_block.get_height()

        if honest_height - self._fork_height < n:
            attack_mine,blocks = bh.mine(adver_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain, 
                                         consensus = self.adver_consensus,
                                         round = round)
            self._log['behavior'] = 'conforming ' + str(honest_height - self._fork_height+1) + '/' +str(n)
        elif honest_height - self._fork_height >= n:
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
                if self._log['behavior'] != 'adopt':
                    self._log['fail'] = self._log['fail'] + 1
                self._log['behavior'] = 'adopt'
                self._attack_success_detect = False
            elif adver_height >= honest_height:
                # 攻击链比诚实链长
                attack_mine,blocks = bh.mine(adver_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain, 
                                         consensus = self.adver_consensus,
                                         round = round)
                self._lastattackblock = self.adver_chain.get_last_block()
                blocks = bh.upload(adver_chain = self.adver_chain,
                        current_miners = current_miners, 
                        round = round,
                        adver_list = self.adver_list,
                        fork_block = self._fork_block, # if self._fork_block != None else self.honest_chain.head,
                        syncLocalChain = False)
                if self._log['behavior'] != 'override':
                    self._attack_success_detect = True

                self._log['behavior'] = 'override'
            # elif adver_height == honest_height - 1:
            #     attack_mine,blocks = bh.mine(adver_list = self.adver_list,
            #                              current_miner = current_miner,
            #                              miner_input = mine_input,
            #                              adver_chain = self.adver_chain,
            #                              consensus = self.adver_consensus,
            #                              round = round)
            #     if attack_mine:
            #         # 等长时，如果挖出来，则立刻发布
            #         blocks = bh.upload(adver_chain = self.adver_chain,
            #                      current_miners = current_miners, 
            #                      round = round,
            #                      adver_list = self.adver_list,
            #                      fork_block = self._fork_block if self._fork_block != None else self.honest_chain.head,
            #                      syncLocalChain = False)
            #         self._lastattackblock = self.adver_chain.get_last_block()
            #         if self._log['behavior'] != 'override':
            #             self._attack_success_detect = True
            #         self._log['behavior'] = 'override'
            #     else:
            #         self._log['behavior'] = 'matching'
            # else:
            #     # 攻击链与诚实链 matching
            #     attack_mine,blocks = bh.mine(adver_list = self.adver_list,
            #                              current_miner = current_miner,
            #                              miner_input = mine_input,
            #                              adver_chain = self.adver_chain, 
            #                              consensus = self.adver_consensus,
            #                              round = round)
            #     self._log['behavior'] = 'matching'
            else:
                # 攻击链与诚实链 matching
                attack_mine,blocks = bh.mine(adver_list = self.adver_list,
                                         current_miner = current_miner,
                                         miner_input = mine_input,
                                         adver_chain = self.adver_chain, 
                                         consensus = self.adver_consensus,
                                         round = round)
                cur_adver_height = self.adver_chain.get_height()
                if cur_adver_height >= honest_height:
                    latest_adver_chain_tip = self.adver_chain.get_last_block()
                    # 如果挖到了与诚实链等高或更高的块，则立刻发布与诚实链等高的块
                    send_chain_tip = self.adver_chain.get_last_block()
                    while send_chain_tip.get_height() > honest_height:
                        send_chain_tip = send_chain_tip.parentblock
                    self._lastattackblock = send_chain_tip
                    self.adver_chain.set_last_block(send_chain_tip) # 让攻击链回退到与诚实链等高的状态，以便上传
                    blocks = bh.upload(adver_chain = self.adver_chain,
                                 current_miners = current_miners, 
                                 round = round,
                                 adver_list = self.adver_list,
                                 fork_block = self._fork_block, # if self._fork_block != None else self.honest_chain.head,
                                 syncLocalChain = False)
                    self.adver_chain.set_last_block(latest_adver_chain_tip) # 恢复攻击链的状态
                    if self._log['behavior'] != 'override':
                        self._attack_success_detect = True
                    self._log['behavior'] = 'override'
                else:
                    self._log['behavior'] = 'matching'

    def clear_record_stage(self, round):
        bh = self.behavior
        self._log['honest_chain']=self.honest_chain.last_block.name,self.honest_chain.last_block.height
        self._log['adver_chain']=self.adver_chain.last_block.name,self.adver_chain.last_block.height
        self._log['fork_block']=(self._fork_block.name  if self._fork_block != None else self.honest_chain.head.name, 
                                 self._fork_block.height  if self._fork_block != None else 0)
        self._log['attacked_block'] = (self._lastattackblock.name if self._lastattackblock != None else None,
                                       self._lastattackblock.height if self._lastattackblock != None else 0)
        # self.__log['other']=self.__log['other']+' fork block is '+self.__fork_blockname
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

    def get_attack_times(self):
        return self._log['success']+self._log['fail']
    
    def info_getter(self,miner_num):
        rate, thr_rate = self.__success_rate(miner_num)
        total_attempts = self._log['success'] + self._log['fail']
        result = {'Success Rate': '{:.4f}'.format(self._log['success']/total_attempts) if total_attempts else '-1',
                'Theory rate in LockstepNetwork': '{:.4f}'.format(thr_rate),
                'Attack times': total_attempts,
                # 'Success times': self._log['success'],
                'Ng': self.attack_arg['Ng'],
                'N': self.attack_arg['N'],
                'attack_fail': self._log['fail'],
                'attack_success': self._log['success']
                }
        if self._premining_enabled:
            result.update({
                'Premining End Condition': self._premining_end_condition,
                'Premining Max Lead': self._premining_max_lead,
                'Premining End Height': self._premining_end_height,
                'Premining End Lead': self._premining_end_lead,
                'Premining Phase': self._phase,
            })
        return result
    
    def __success_rate(self,miner_num):
        if self._log['success'] != 0 or self._log['fail'] != 0:
            rate = self._log['success']/(self._log['success']+self._log['fail'])
            ## 计算理论成功率
            tmp = 0
            n = self.attack_arg['N']
            ng = self.attack_arg['Ng']
            beta = len(self.adver_list)/(miner_num-len(self.adver_list))
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
                        tmp = tmp + 1/(2**(n+j))*(math.factorial(j+n-1))/((math.factorial(j))*(math.factorial(n-1)))*((n-j+1)/(ng+1))
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


