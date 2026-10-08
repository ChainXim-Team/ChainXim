'''
定义honestminging攻击
'''
import random

import attack.attack_type as aa
import global_var
from data import Block, Chain
import copy


class BalanceAttack(aa.AttackType):
    '''
    算力攻击
    '''

    def __init__(self) -> None:
        super().__init__()
        self._log = {
            # 'round': 0,
            'honest_chain': None,
            'adver_chain': None,
            'fork_block': None
        }
        self._fork_block: list[Block] = []
        self._simplifylog = {}
        self.attack_height_vt = {}

    def renew_stage(self, round):
        ## 1. renew stage
        newest_block, mine_input = self.behavior.renew(miner_list=self.adver_list,
                                                       honest_chain_prp=self.honest_chain_prp,
                                                       honest_chain_vt=self.honest_chain_vt, round=round)
        return newest_block, mine_input

    def attack_stage(self, round, mine_input):
        ## 2. attack stage
        attack_flag = global_var.get_attack_flag_BA()
        if attack_flag:
            heights_prp = global_var.get_height_BA()
            # 删除已经完成攻击的高度
            keys_to_remove = [key for key in self.attack_height_vt if key not in heights_prp]
            for key in keys_to_remove:
                del self.attack_height_vt[key]
            # 记录需要攻击的提议者高度下对应的投票者高度
            for height in heights_prp:
                if height not in self.attack_height_vt:
                    # 获取所有 vtchain 的高度并将其作为列表保存
                    vt_heights = [vtchain.last_block.height for vtchain in self.honest_chain_vt]
                    self.attack_height_vt[height] = vt_heights
                    print(f'has record: {self.attack_height_vt}')
                    global_var.set_height_BA_vt(self.attack_height_vt)
            for height in heights_prp:
                minority_block = self.honest_chain_prp.get_minority_block(height)
                votecounts = global_var.get_vtcount()
                print(f'votecounts has {votecounts}')
                if minority_block is not None:
                    vote = votecounts.get(minority_block.name)
                    print('global votes:', votecounts)
                    print(f'height {height} minority block {minority_block} has votes {vote}')

        current_miner = random.choice(self.adver_list)
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
        if attack_flag:
            print('in balance attack')
            attack_mine, block = self.behavior.mine(miner_list=self.adver_list,
                                                    current_miner=current_miner,
                                                    miner_input=mine_input,
                                                    adver_chain_prp=self.adver_chain_prp,
                                                    global_chain_prp=self.global_chain_prp,
                                                    adver_chain_vt=self.adver_chain_vt,
                                                    global_chain_vt=self.global_chain_vt,
                                                    consensus=self.adver_consensus,
                                                    round=round,
                                                    necessary_blocks=[minority_block])
        else:
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
            self._fork_block = [block]
            print('in upload')
            self.behavior.upload(network=self.network,
                                 adver_chain_prp=self.adver_chain_prp,
                                 adver_chain_vt=self.adver_chain_vt,
                                 current_miner=current_miner,
                                 round=round,
                                 miner_list=self.adver_list,
                                 fork_block=self._fork_block,
                                 )
        else:
            self.behavior.wait()

    def clear_record_stage(self, round):
        ## 3. clear and record stage
        self.behavior.clear(miner_list=self.adver_list)  # 清空
        # self._log['round'] = round
        self._log['honest_chain_prp'] = self.honest_chain_prp.last_block.name + ' Height:' + str(
            self.honest_chain_prp.last_block.height)
        self._log['adver_chain_prp'] = self.adver_chain_prp.last_block.name + ' Height:' + str(
            self.adver_chain_prp.last_block.height)
        # 记录每条honest投票者链的数据
        self._log['honest_chain_vt'] = [chain.last_block.name + ' Height:' + str(chain.last_block.height) for chain in
                                        self.honest_chain_vt]
        # 记录每条adversary投票者链的数据
        self._log['adver_chain_vt'] = [chain.last_block.name + ' Height:' + str(chain.last_block.height) for chain in
                                       self.adver_chain_vt]
        self.resultlog2txt(round)

    def excute_this_attack_per_round(self, round):

        ## 1. renew stage
        newest_block, mine_input = self.renew_stage(round)
        ## 2. attack stage
        self.attack_stage(round, mine_input)
        ## 3. clear and record stage
        self.clear_record_stage(round)

    def info_getter(self):

        loop_block = self.global_chain_prp.last_block
        main_chain_height = loop_block.height
        adver_block_num = 0
        while (loop_block):
            if loop_block.isAdversaryBlock:
                adver_block_num += 1
            loop_block = loop_block.parentblock
        return {'Success Rate': '{:.4f}'.format(adver_block_num / main_chain_height),
                'Theory rate in SynchronousNetwork': '{:.4f}'.format(len(self.adver_list) / len(self.miner_list))}

    def resultlog2txt(self, round):
        if self._simplifylog != self._log:
            self._simplifylog = copy.deepcopy(self._log)
            ATTACK_RESULT_PATH = global_var.get_attack_result_path()
            with open(ATTACK_RESULT_PATH / f'Attack Log.txt', 'a') as f:
                print(self._log, round, '\n', file=f)


