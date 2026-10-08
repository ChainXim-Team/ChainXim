import copy
import logging
import math
import random
import time
import os

import numpy as np
import matplotlib.pyplot as plt

import consensus
import global_var
import network
from attack.adversary import Adversary
from data import Block, Chain
from external import chain_growth, chain_quality, common_prefix
from functions import for_name, calculate_h_t
from miner import Miner, network_interface

from pyinstrument import Profiler  # 导入 pyinstrument

logger = logging.getLogger(__name__)


class Environment(object):

    def __init__(self, attack_param: dict = None,
                 consensus_param: dict = None, network_param: dict = None,
                 genesis_blockheadextra: dict = None, genesis_blockextra: dict = None):
        '''initiate the running environment

        Param
        -----
        attack_param: attack parameters (dict)
        consensus_param: consensus parameters (dict)
        network_param: network parameters (dict)
        genesis_blockheadextra: initialize variables in the head of genesis block (dict)
        genesis_blockextra: initialize variables in the genesis block (dict)

        '''
        # environment parameters
        self.miner_num = global_var.get_miner_num()
        self.total_round = 0
        # configure extra genesis block info
        consensus_type: consensus.Consensus = for_name(global_var.get_consensus_type())
        consensus_type.genesis_blockheadextra = genesis_blockheadextra
        consensus_type.genesis_blockextra = genesis_blockextra
        # generate miners
        self.miners: list[Miner] = []
        for miner_id in range(self.miner_num):
            self.miners.append(Miner(miner_id, consensus_param))
        self.envir_create_global_chain()
        # self.checkpoint = None  # Note: activated with the common prefix function
        # evaluation
        self.max_suffix = 10
        # 每轮结束时，各个矿工的链与common prefix相差区块个数的分布
        self.cp_pdf = np.zeros((1, self.max_suffix))
        self.cp_pdf_vt = np.zeros((global_var.get_vtnum(), self.max_suffix))
        # 每轮结束时，把主链减少k个区块，是否被包含在矿工的区块链里面
        self.cp_cdf_k = np.zeros((1, self.max_suffix))
        # generate network
        self.network: network.Network = for_name(global_var.get_network_type())(self.miners)
        self.network.set_net_param(**network_param)

        # generate adversary
        self.adversary = Adversary(
            adver_num=attack_param['adver_num'],
            attack_type=attack_param['attack_type'],
            adversary_ids=attack_param['adversary_ids'],
            network_type=self.network,
            consensus_type=global_var.get_consensus_type(),
            miner_list=self.miners,
            # eclipse = attack_param['eclipse'],
            global_chain_prp=self.global_chain_prp,
            global_chain_vt=self.global_vt_chains,
            adver_consensus_param=consensus_param,
            attack_arg=attack_param['attack_arg'])
        # get adversary IDs
        adversary_ids = self.adversary.get_adver_ids()
        global_var.set_adver_ids(adversary_ids)
        # add a line in chain data to distinguish adversaries from non-adversaries
        CHAIN_DATA_PATH = global_var.get_chain_data_path()
        for miner in self.miners:
            with open(CHAIN_DATA_PATH / f'chain_data{str(miner.miner_id)}.txt', 'a') as f:
                print(f"isAdversary: {miner.isAdversary}\n", file=f)
        parameter_str = ('Parameters:\n' +
                         f'Miner Number: {self.miner_num} \n' +
                         f'Consensus Protocol: {consensus_type.__name__} \n' +
                         f'Network Type: {type(self.network).__name__} \n' +
                         f'Network Param:  {network_param} \n' +
                         f'Consensus Param: {consensus_param} \n')
        if adversary_ids:
            parameter_str += f'Adversary Miners: {adversary_ids} \n'
            parameter_str += f'Attack Execute Type: {self.adversary.get_attack_type_name()}'
            # parameter_str += f'  (Eclipse: {self.adversary.get_eclipse()}) \n'
            parameter_str += f"  (Adversary's q: {self.adversary.get_adver_q()}) \n"
        if isinstance(self.miners[0].NIC, network_interface.NICWithTp):
            parameter_str += f'Block Size: {global_var.get_blocksize()} \n'
        print(parameter_str)
        with open(global_var.get_result_path() / 'parameters.txt', 'w+') as conf:
            print(parameter_str, file=conf)

    def envir_create_global_chain(self):
        '''create global chain and its genesis block by copying
          local chain from the first miner.'''
        self.global_chain_prp = Chain()
        self.global_chain_prp.add_blocks(blocks=copy.deepcopy(self.miners[0].consensus.local_chain_prp.head))
        self.global_vt_chains = []
        for vt_chain in self.miners[0].consensus.local_chain_vt:
            # 创建一个新的全局投票链实例
            global_chain_vt = Chain()
            # 复制对应vtChain的头部状态
            global_chain_vt.add_blocks(blocks=copy.deepcopy(vt_chain.head))
            # 将这个新创建并初始化的全局链添加到列表中
            self.global_vt_chains.append(global_chain_vt)
        # self.global_chain.head = copy.deepcopy(self.miners[0].consensus.local_chain.head)
        # self.global_chain.lastblock = self.global_chain.head

    def exec(self, num_rounds, max_height, process_bar_type):
        '''
        调用当前miner的BackboneProtocol完成mining
        当前miner用add_block_direct添加上链
        之后gobal_chain用深拷贝的add_block_copy上链
        '''

        # profiler = Profiler()  # 创建Profiler实例
        # profiler.start()  # 开始性能分析

        if process_bar_type != 'round' and process_bar_type != 'height':
            raise ValueError('process_bar_type should be \'round\' or \'height\'')
        ## 开始循环
        t_0 = time.time()  # 记录起始时间
        cached_height = self.global_chain_prp.get_height()

        qualified_votes_latency = {}
        threshold = 0
        vote_counts = global_var.get_vtcount()
        perm_prp = []
        m = global_var.get_vtnum()
        fork_prp = []
        BA_height = []

        for round in range(1, num_rounds + 1):

            inputfromz = round  # 生成输入

            adver_tmpflag = 1
            if self.adversary.get_adver_num() != 0:
                adverflag = random.randint(1, self.adversary.get_adver_num())

            for miner in self.miners:
                miner.input_tape.append(("INSERT", inputfromz))

                # 攻击者
                if miner.isAdversary:
                    if adver_tmpflag == adverflag:
                        attack_flag = self.adversary.excute_per_round(round=round)
                        global_var.set_attack_flag_ds(attack_flag)
                    adver_tmpflag = adver_tmpflag + 1
                    continue

                # 诚实矿工 run backbone protocol

                new_msgs = miner.BackboneProtocol(round)

                if new_msgs is not None:
                    # self.network.access_network(new_msgs,temp_miner.miner_id,round)
                    for msg in new_msgs:
                        if isinstance(msg, Block):
                            if msg.index == 1:
                                self.global_chain_prp._add_block_forcibly(msg)
                                global_var.set_arrive_time_prp(msg.name, round)
                            elif msg.index == 0:
                                tx = global_var.get_txnum()
                                global_var.set_txho(tx)
                                global_var.add_tx(f"TX{tx}")
                                global_var.set_arrive_time_tx(msg.name,round)
                            elif msg.index < (global_var.get_vtnum() + 2):
                                self.global_vt_chains[msg.index - 2]._add_block_forcibly(msg)

                miner.clear_tapes()

            # diffuse(C)
            self.network.diffuse(round)
            self.assess_common_prefix(round)
            # self.assess_common_prefix_k() # TODO 放到view(),评估独立于仿真过程

            vote_counts = {}
            vote_counts_time = {}  # 用于记录每个区块的得票时间
            data_to_prp_latency = {}
            qualified_votes_latency = {}

            confirm_depth = global_var.get_depth()
            calculate_depth = confirm_depth - 1

            vote_depths = {}
            vote_counts_height = {}

            if global_var.get_attack_execute_type() != 'HonestMining':

                for vt_chain in self.global_vt_chains:
                    # 从vt_chain的最后一个区块开始
                    current_block = vt_chain.get_last_block()
                    chain_height = current_block.height
                    # for _ in range(calculate_depth):  # 你这里的0应该是实际要移动的区块数
                    #     if current_block and current_block.name != 'B0':
                    #         current_block = current_block.parentblock
                    while current_block and current_block.name != 'B0':  # 持续直到创世块
                        # 统计当前区块的投票结果
                        k_conf = 1
                        k_confirmed_block = current_block
                        for _ in range(calculate_depth):  # 你这里的0应该是实际要移动的区块数
                            if k_confirmed_block and k_confirmed_block.name != 'B0':
                                k_confirmed_block = k_confirmed_block.parentblock
                            else:
                                k_conf = 0
                        if k_conf == 1:
                            for voted_block in k_confirmed_block.vtonprp:
                                vote_counts[voted_block.name] = vote_counts.get(voted_block.name, 0) + 1
                                if voted_block.name not in vote_counts_time:
                                    vote_counts_time[voted_block.name] = []
                                vote_counts_time[voted_block.name].append(current_block.blockhead.timestamp)
                            # 移动到前一个区块
                        current_block = current_block.parentblock

                global_var.write_vtcount(vote_counts)

                threshold = global_var.get_vote_threshold()

                for prpblock in self.global_chain_prp:
                    # 检查该prpblock的得票数是否大于等于threshold
                    vote_count = vote_counts.get(prpblock.name, 0)
                    if vote_count >= threshold:
                        # 对得票时间戳列表进行排序
                        vote_times = sorted(vote_counts_time[prpblock.name])
                        # 取第 threshold 个时间作为确认时间
                        print(f'threshold:{threshold}')
                        confirmation_time = vote_times[threshold - 1]

                        for tx in prpblock.txblock:
                            # 查找_var_dict['ARRIVE_TIME']中对应的tx的到达时间
                            arrive_round = global_var.get_ar_time_tx().get(tx, None)
                            if arrive_round is not None:
                                # 计算latency，使用确认时间代替 round
                                latency = confirmation_time - arrive_round
                                latency_data = prpblock.blockhead.timestamp - arrive_round
                                # 更新data_to_prp_latency
                                if tx not in data_to_prp_latency:
                                    data_to_prp_latency[tx] = latency_data
                                # 更新qualified_votes_latency
                                if tx not in qualified_votes_latency:
                                    qualified_votes_latency[tx] = latency

                height_block_count = {}

                for prpblock in self.global_chain_prp:
                    # 检索当前prpblock的得票数
                    # vote_count = vote_counts.get(prpblock.name, 0)
                    if prpblock.height in height_block_count:
                        height_block_count[prpblock.height] += 1
                    else:
                        height_block_count[prpblock.height] = 1
                print('height_count')
                print(height_block_count)
                # 遍历 height_block_count
                if global_var.get_attack_execute_type() == 'BalanceAttack':
                    for key, value in height_block_count.items():
                        if value > 1:
                            # 如果 key 不在 BA_height 中
                            if key not in BA_height:
                                # 追加到 BA_height
                                global_var.set_attack_flag_BA(True)
                                BA_height.append(key)
                                # 调用 global_var.set_height_BA()，假设 global_var 已经定义
                                global_var.set_height_BA(key)
                                heights = global_var.get_height_BA()
                                print('balance attack begin at height:')
                                for height in heights:
                                    print(height)

                for prpblock in self.global_chain_prp:
                    # is_unique_at_height = height_block_count[prpblock.height] == 1
                    is_unique_at_height = 1
                    if prpblock.name not in perm_prp and is_unique_at_height:
                        # print('jin zhe li le')
                        # vote_depth = vote_depths.get(prpblock.name, 0)
                        # h_t_input = vote_depth / (m * 0.1)
                        # h_t_value = calculate_h_t(0.1, 0.3, h_t_input)
                        if prpblock.name not in vote_counts:
                            vote_counts[prpblock.name] = 0
                            global_var.write_vtcount(vote_counts)
                        vote_count = vote_counts.get(prpblock.name, 0)

                        #
                        # prpath = 'D:/votejilu.txt'  # 请将 'your_file_path_here.txt' 替换为你指定的文件路径
                        # with open(file_path, 'a') as f:
                        #     f.write(f"at round {round} prpblock {prpblock.name} has vote {vote_count}\n")
                        # vote_count_height = vote_counts_height.get(prpblock.height, 0)
                        # # 检查该prpblock的得票数是否大于等于threshold
                        # vote_count = vote_counts.get(prpblock.name, 0)
                        # print(f'now prpblock{prpblock.name} has value{h_t_value}')
                        # if h_t_value > 0.584:
                        if vote_count >= global_var.get_vote_threshold():
                            # 遍历prpblock.txblock中的每个tx
                            current_cfheight = global_var.get_cfheight()
                            if current_cfheight:
                                current_cfheight_max = max(current_cfheight)
                            else:
                                current_cfheight_max = 0  # 如果列表为空，可以设置为 None 或其他默认值
                            cfheigts = global_var.get_cfheight()
                            # if prpblock.height > current_cfheight_max:
                            if prpblock.height not in cfheigts:
                                global_var.set_cfheight(prpblock.height)
                                ba_height_attacking = global_var.get_height_BA()
                                confirm_height = global_var.get_cfheight()
                                heights_to_remove = [height for height in ba_height_attacking if height in confirm_height]
                                # 删除这些高度
                                for height in heights_to_remove:
                                    global_var.remove_height_BA(height)
                                    print(f'balance attack at height{height} finish at round {round}')
                                    for miner in self.miners:
                                        if miner.isAdversary:
                                            for chain_num in range(len(miner.consensus.votesOnPrpBks)):
                                                # 过滤掉 votesOnPrpBks 中高度为 height 的区块
                                                votes_on_prp_bks = miner.consensus.votesOnPrpBks[chain_num]
                                                miner.consensus.votesOnPrpBks[chain_num] = [
                                                    block for block in votes_on_prp_bks if block.height != height
                                                ]

                                if global_var.get_height_BA() == []:
                                    global_var.set_attack_flag_BA(False)

                            perm_prp.append(prpblock.name)
                            arrive_round = global_var.get_ar_time_prp().get(prpblock.name, None)
                            if arrive_round is not None:
                                # 计算latency
                                latency = round - arrive_round
                                if prpblock.name not in qualified_votes_latency:
                                    qualified_votes_latency[prpblock.name] = latency
                                    attack_height = global_var.get_ds_height()
                                    if attack_height == prpblock.height and not prpblock.isAdversaryBlock:
                                        latency_attackblock = latency
                                        if attack_height == prpblock.height and not prpblock.isAdversaryBlock:
                                            latency_attackblock = latency
                                            # 记录所有投票给 prpblock 的 vtblock 信息（名字、时间戳和 vt_chain 索引）
                                            prpblock_votes = []
                                            vote_timestamps = {}  # 保留原有逻辑，用于记录所有投票详细信息

                                            for vt_chain_idx, vt_chain in enumerate(self.global_vt_chains):
                                                # 从 vt_chain 的最后一个区块开始
                                                current_block = vt_chain.get_last_block()
                                                chain_height = current_block.height

                                                while current_block and current_block.name != 'B0':  # 持续直到创世块
                                                    # 统计当前区块是否满足确认深度要求
                                                    k_conf = 1
                                                    k_confirmed_block = current_block
                                                    for _ in range(calculate_depth):
                                                        if k_confirmed_block and k_confirmed_block.name != 'B0':
                                                            k_confirmed_block = k_confirmed_block.parentblock
                                                        else:
                                                            k_conf = 0
                                                    if k_conf == 1:
                                                        for voted_block in k_confirmed_block.vtonprp:
                                                            # 记录投票及其详细信息
                                                            if voted_block.name not in vote_timestamps:
                                                                vote_timestamps[voted_block.name] = []
                                                            vote_timestamps[voted_block.name].append({
                                                                'timestamp': current_block.blockhead.timestamp,
                                                                'chain_idx': vt_chain_idx,
                                                                'block_name': current_block.name,
                                                                'block_height': current_block.height
                                                            })

                                                            # 判断当前投票是否针对 prpblock
                                                            if voted_block.name == prpblock.name:
                                                                prpblock_votes.append({
                                                                    'vt_chain_idx': vt_chain_idx,
                                                                    'vtblock_name': current_block.name,
                                                                    'timestamp': current_block.blockhead.timestamp
                                                                })
                                                    # 移动到前一个区块
                                                    current_block = current_block.parentblock

                                            # 对所有投给 prpblock 的投票信息按照 timestamp 进行排序
                                            sorted_votes = sorted(prpblock_votes, key=lambda x: x['timestamp'])
                                            print(f"Votes for prpblock {prpblock.name} (sorted by timestamp):")
                                            for vote in sorted_votes:
                                                print(
                                                    f"vtblock: {vote['vtblock_name']}, timestamp: {vote['timestamp']}")

                                            # 如果排序后票数达到阈值，则取第 threshold 个投票对应的 vt_chain_idx
                                            if len(sorted_votes) >= threshold:
                                                threshold_vote_info = sorted_votes[threshold - 1]
                                                threshold_chain_index = threshold_vote_info['vt_chain_idx']
                                                global_var.set_threshold_num(threshold_chain_index)
                                                print(
                                                    f"Threshold reached at vt_chain_idx: {threshold_chain_index}")
                                            else:
                                                print("Threshold not reached")

                            to_remove = []
                            for block in fork_prp:
                                if block.height <= prpblock.height:
                                    perm_prp.append(block.name)
                                    arrive_round = global_var.get_ar_time().get(block.name, None)
                                    if arrive_round is not None:
                                        # 计算latency
                                        latency = round - arrive_round
                                        if block.name not in qualified_votes_latency:
                                            qualified_votes_latency[block.name] = latency
                                        to_remove.append(block)
                            for block in to_remove:
                                fork_prp.remove(block)
                    elif prpblock.name not in perm_prp:
                        fork_prp.append(prpblock)

            global_var.set_global_prpchain(self.global_chain_prp)

            # 全局链高度超过max_height之后就提前停止
            current_height = self.global_chain_prp.get_height()
            if current_height > max_height:
                break
            # 根据process_bar_type决定进度条的显示方式
            if process_bar_type == 'round':
                self.process_bar(round, num_rounds, t_0, 'round/s')
            elif current_height > cached_height and process_bar_type == 'height':
                cached_height = current_height
                self.process_bar(current_height, max_height, t_0, 'block/s')

            continue_flag = global_var.get_onetime_double_spending()
            # if round % 10000 == 0:
            #     file_path = f'D:/p.txt'  # 请将 'your_file_path_here.txt' 替换为你指定的文件路径
            #     with open(file_path, 'a') as f:
            #         f.write(f"round:{round}\n")
            #     file_path = f'D:/p_p.txt'  # 请将 'your_file_path_here.txt' 替换为你指定的文件路径
            #     with open(file_path, 'a') as f:
            #         f.write(f"round:{round}\n")
            #     #统计global_chain_prp和global_vt_chains的区块数量
            #     blocks_count_prp = -1
            #     for block in self.global_chain_prp:
            #         blocks_count_prp += 1
            #     file_path = f'D:/typical_count.txt'  # 请将 'your_file_path_here.txt' 替换为你指定的文件路径
            #     with open(file_path, 'a') as f:
            #         f.write(f"prpchain:{blocks_count_prp} and p:{blocks_count_prp / round}\n")
            #
            #     file_path = f'D:/p.txt'  # 请将 'your_file_path_here.txt' 替换为你指定的文件路径
            #     with open(file_path, 'a') as f:
            #         f.write(f"{blocks_count_prp / round}\n")
            #     file_path = f'D:/p_p.txt'  # 请将 'your_file_path_here.txt' 替换为你指定的文件路径
            #     with open(file_path, 'a') as f:
            #         block_generated = global_var.get_blocks_generated()
            #         f.write(f"{block_generated}\n")
            #
            #     for vt_chain in self.global_vt_chains:
            #         blocks_count_vt = -1
            #         for block in vt_chain:
            #             blocks_count_vt += 1
            #         file_path = f'D:/typical_count.txt'  # 请将 'your_file_path_here.txt' 替换为你指定的文件路径
            #         with open(file_path, 'a') as f:
            #             f.write(f"vtchain:{blocks_count_vt} and p:{blocks_count_vt / round}\n")
            #         file_path = f'D:/p.txt'  # 请将 'your_file_path_here.txt' 替换为你指定的文件路径
            #         with open(file_path, 'a') as f:
            #             f.write(f"{blocks_count_vt / round}\n")





            if not continue_flag:
                break
        ds_success_times = global_var.get_ds_success_times()
        print(f"ds_success_times: {ds_success_times}")
        # return ds_success_times, latency_attackblock, threshold_chain_index
        return ds_success_times

            # # 每轮结束时进行绘图
            # vote_counts = global_var.get_vtcount()
            # max_votes_per_height = {}
            # for block in self.global_chain_prp:
            #     if block.height not in max_votes_per_height or \
            #             vote_counts.get(block.name, 0) > vote_counts.get(max_votes_per_height[block.height].name,
            #                                                                 0) or \
            #             (vote_counts.get(block.name, 0) == vote_counts.get(max_votes_per_height[block.height].name,
            #                                                                 0) and block.blockhash <
            #                 max_votes_per_height[
            #                      block.height].blockhash):
            #         max_votes_per_height[block.height] = block
            #
            # dot = self.global_chain_prp.ShowStructureWithGraphviz(dot=None, chain_id='prpchain', prpchain=None,
            #                                                           vote_counts=vote_counts,
            #                                                           max_votes_per_height=max_votes_per_height)
            # for i in range(global_var.get_vtnum()):
            #     dot = self.global_vt_chains[i].ShowStructureWithGraphviz(dot=dot, chain_id=f'vtchain_{i}',
            #                                                                  prpchain=None)
            #
            # round_result_path = global_var.get_result_path() / f"blockchain_visualization_round_{round}"
            # os.makedirs(round_result_path, exist_ok=True)  # 创建目录
            # dot.render(directory=round_result_path, format='svg', view=False)
        prp_to_confirm = None
        data_to_prp_latency = None

        if not global_var.get_onetime_double_spending_flag():
            if global_var.get_attack_execute_type() == 'HonestMining':
                vote_counts = {}
                vote_counts_time = {}  # 用于记录每个区块的得票时间
                data_to_prp_latency = {}
                qualified_votes_latency = {}
                prp_to_confirm = {}

                confirm_depth = global_var.get_depth()
                calculate_depth = confirm_depth - 1
                for vt_chain in self.global_vt_chains:
                    # 从vt_chain的最后一个区块开始
                    current_block = vt_chain.get_last_block()
                    chain_height = current_block.height
                    # for _ in range(calculate_depth):  # 你这里的0应该是实际要移动的区块数
                    #     if current_block and current_block.name != 'B0':
                    #         current_block = current_block.parentblock
                    while current_block and current_block.name != 'B0':  # 持续直到创世块
                        # 统计当前区块的投票结果
                        k_conf = 1
                        k_confirmed_block = current_block
                        for _ in range(calculate_depth):  # 你这里的0应该是实际要移动的区块数
                            if k_confirmed_block and k_confirmed_block.name != 'B0':
                                k_confirmed_block = k_confirmed_block.parentblock
                            else:
                                k_conf = 0
                        if k_conf == 1:
                            for voted_block in k_confirmed_block.vtonprp:
                                vote_counts[voted_block.name] = vote_counts.get(voted_block.name, 0) + 1
                                if voted_block.name not in vote_counts_time:
                                    vote_counts_time[voted_block.name] = []
                                vote_counts_time[voted_block.name].append(current_block.blockhead.timestamp)
                            # 移动到前一个区块
                        current_block = current_block.parentblock

                global_var.write_vtcount(vote_counts)

                threshold = global_var.get_vote_threshold()

                for prpblock in self.global_chain_prp:
                    # 检查该prpblock的得票数是否大于等于threshold
                    vote_count = vote_counts.get(prpblock.name, 0)
                    if vote_count >= threshold:
                        # 对得票时间戳列表进行排序
                        vote_times = sorted(vote_counts_time[prpblock.name])
                        # 取第 threshold 个时间作为确认时间
                        confirmation_time = vote_times[threshold - 1]
                        latency_prp = confirmation_time - prpblock.blockhead.timestamp

                        for tx in prpblock.txblock:
                            # 查找_var_dict['ARRIVE_TIME']中对应的tx的到达时间
                            arrive_round = global_var.get_ar_time_tx().get(tx, None)
                            if arrive_round is not None:
                                # 计算latency，使用确认时间代替 round
                                latency = confirmation_time - arrive_round

                                latency_data = prpblock.blockhead.timestamp - arrive_round
                                # 更新data_to_prp_latency
                                if tx not in data_to_prp_latency:
                                    data_to_prp_latency[tx] = latency_data
                                # 更新qualified_votes_latency
                                if tx not in qualified_votes_latency:
                                    qualified_votes_latency[tx] = latency
                        if prpblock.name not in prp_to_confirm:
                            prp_to_confirm[prpblock.name] = latency_prp
            if qualified_votes_latency:
                total_latency = sum(qualified_votes_latency.values())
                num_of_latencies = len(qualified_votes_latency)
                average_latency = total_latency / num_of_latencies
            else:
                average_latency = 0  # 如果没有latency数据，则平均数为0
            if prp_to_confirm:
                total_latency = sum(prp_to_confirm.values())
                num_of_latencies = len(prp_to_confirm)
                average_latency_prp_to_confirm = total_latency / num_of_latencies
            else:
                average_latency_prp_to_confirm = 0
            if data_to_prp_latency:
                total_latency = sum(data_to_prp_latency.values())
                num_of_latencies = len(data_to_prp_latency)
                average_latency_data_to_prp = total_latency / num_of_latencies
            else:
                average_latency_data_to_prp = 0  # 如果没有latency数据，则平均数为0
            arr = global_var.get_ar_time()
            if global_var.get_attack_execute_type() != 'HonestMining':
                ds_success_times = global_var.get_ds_success_times()
                ds_try_times = global_var.get_ds_try_times()
                ds_success_rate = ds_success_times / ds_try_times
                file_path = f'D:/double-spending_count.txt'  # 请将 'your_file_path_here.txt' 替换为你指定的文件路径
                with open(file_path, 'a') as f:
                    f.write(f"ds_try_times:{ds_try_times} ds_success_rate:{ds_success_rate}\n"
                            f"平均总延迟（latency）:{average_latency}\n"
                            f"平均交易接收延迟（latency）:{average_latency_data_to_prp}\n")
            file_path = f'D:/double-spending_count.txt'  # 请将 'your_file_path_here.txt' 替换为你指定的文件路径
            with open(file_path, 'a') as f:
                f.write(f"平均总延迟（latency）:{average_latency}\n"
                        f"平均交易接收延迟（latency）:{average_latency_data_to_prp}\n"
                        f"average_latency_prp_to_confirm:{average_latency_prp_to_confirm}\n"
                        f"prp_to_confirm：{prp_to_confirm}"
                        )
            # print(f'ds_success_rate: {ds_success_rate}')
            print(f"vote counts:", vote_counts)
            print("\n")
            print("latency:", qualified_votes_latency)
            print("平均延迟（latency）:", average_latency)
            print("ARR TIME:", arr)
            for vt_chain in self.global_vt_chains:
                # 从 vt_chain 的最后一个区块开始
                current_block = vt_chain.get_last_block()

                while current_block and current_block.name != 'B0':  # 持续直到创世块
                    # 打印当前区块的名字
                    print(f"Current Block: {current_block.name}")

                    # 打印 current_block.vtonprp 中每个 Block 的名字
                    for voted_block in current_block.vtonprp:
                        print(f"  Voted Block: {voted_block.name}")

                    # 移动到前一个区块
                    current_block = current_block.parentblock

            self.total_round = self.total_round + round



            # profiler.stop()  # 停止性能分析

            # # 将性能分析结果保存到文件
            # result_path = global_var.get_result_path() / 'profile_exec_result.txt'
            # with open(result_path, 'w') as f:
            #     f.write(profiler.output_text(unicode=True, color=False))
            #
            # print(f"性能分析结果已保存到 {result_path}")

        # profiler.stop()  # 停止性能分析

        # # 将性能分析结果保存到文件
        # result_path = global_var.get_result_path() / 'profile_exec_result.txt'
        # with open(result_path, 'w') as f:
        #     f.write(profiler.output_text(unicode=True, color=False))
        #
        # print(f"性能分析结果已保存到 {result_path}")

    def assess_common_prefix(self, round):
        # Common Prefix Property for global chain
        cp = self.global_chain_prp.get_last_block()
        for i in range(1, self.miner_num):
            if not self.miners[i].isAdversary:
                cp = common_prefix(cp, self.miners[i].consensus.local_chain_prp)
        len_cp = cp.height
        for i in range(0, self.miner_num):
            len_suffix = self.miners[i].consensus.local_chain_prp.get_height() - len_cp
            if len_suffix >= 0 and len_suffix < self.max_suffix:
                self.cp_pdf[0, len_suffix] += 1

        # Common Prefix Property for global VT chains
        for j in range(0, global_var.get_vtnum()):
            cp_vt = self.global_vt_chains[j].get_last_block()
            for i in range(1, self.miner_num):
                if not self.miners[i].isAdversary:
                    cp_vt = common_prefix(cp_vt, self.miners[i].consensus.local_chain_vt[j])
            len_cp_vt = cp_vt.height
            for i in range(0, self.miner_num):
                len_suffix = self.miners[i].consensus.local_chain_vt[j].get_height() - len_cp_vt
                if len_suffix >= 0 and len_suffix < self.max_suffix:
                    self.cp_pdf_vt[j, len_suffix] += 1
        # logger.info("round %d: checkpoint %s", round, self.checkpoint.name)

    def assess_common_prefix_k(self):
        # 一种新的计算common prefix的方法
        # 每轮结束后，砍掉主链后
        cp_k = self.global_chain.get_last_block()
        cp_stat = np.zeros((1, self.miner_num))
        for k in range(self.max_suffix):
            # 当所有矿工的链都达标后，后面的都不用算了，降低计算复杂度
            if cp_k is None or np.sum(cp_stat) == self.miner_num-self.adversary.get_adver_num():
                self.cp_cdf_k[0, k] += self.miner_num-self.adversary.get_adver_num()
                continue
            cp_sum_k = 0
            for i in range(self.miner_num):
                if self.miners[i].isAdversary:
                    continue
                if cp_stat[0, i] == 1:
                    cp_sum_k += 1
                    continue
                if cp_k == common_prefix(cp_k, self.miners[i].consensus.local_chain):
                    cp_stat[0, i] = 1
                    cp_sum_k += 1
            self.cp_cdf_k[0, k] += cp_sum_k
            cp_k = cp_k.parentblock

    def view(self) -> dict:
        # 展示一些仿真结果
        # print('\n')
        # print("Global Tree Structure:", "")
        # self.global_chain.ShowStructure1()
        # print("End of Global Tree", "")

        # Evaluation Results
        total_stats = self.global_chain_prp.CalculateStatistics(self.total_round)

        # Step 2: 累加统计数据
        for i, vt_chain in enumerate(self.global_vt_chains):
            # 计算每条投票者链的统计数据
            vt_stats = vt_chain.CalculateStatistics(self.total_round)

            # 累加统计数据
            total_stats["num_of_generated_blocks"] += vt_stats["num_of_generated_blocks"]
            total_stats["num_of_valid_blocks"] += vt_stats["num_of_valid_blocks"]
            global_var.set_thcount(i, vt_stats["num_of_valid_blocks"])
            total_stats["num_of_stale_blocks"] += vt_stats["num_of_stale_blocks"]
            total_stats["num_of_forks"] += vt_stats["num_of_forks"]
            total_stats["num_of_heights_with_fork"] += vt_stats["num_of_heights_with_fork"]
            # 注意：其他需要特殊处理的统计将在后续步骤中计算
        total_stats["num_of_generated_blocks"] += global_var.get_txnum()

        # Step 3: 计算平均值和比率
        # 注意：这里需要根据累加后的数据重新计算平均值和比率
        blocksize = global_var.get_blocksize()
        total_stats["average_block_time_main"] = self.total_round / total_stats["num_of_valid_blocks"]
        total_stats["block_throughput_main"] = total_stats["num_of_valid_blocks"] / self.total_round
        total_stats["throughput_main_MB"] = blocksize * total_stats["block_throughput_main"]
        total_stats["average_block_time_total"] = self.total_round / total_stats["num_of_generated_blocks"]
        total_stats["block_throughput_total"] = 1 / total_stats["average_block_time_total"]
        total_stats["throughput_total_MB"] = blocksize * total_stats["block_throughput_total"]
        total_stats["fork_rate"] = total_stats["num_of_heights_with_fork"] / total_stats["num_of_valid_blocks"]
        total_stats["stale_rate"] = total_stats["num_of_stale_blocks"] / total_stats["num_of_generated_blocks"]

        total_stats.update({'total_round': self.total_round})
        # Chain Growth Property
        growth = 0
        num_honest = 0
        for i in range(self.miner_num):
            if not self.miners[i].isAdversary:
                growth = growth + chain_growth(self.miners[i].consensus.local_chain_prp)
                for j in range(global_var.get_vtnum()):
                    growth = growth + chain_growth(self.miners[i].consensus.local_chain_vt[j])
                num_honest = num_honest + 1
        growth = growth / num_honest
        total_stats.update({
            'average_chain_growth_in_honest_miners\'_chain': growth
        })
        # Common Prefix Property
        total_stats.update({
            'common_prefix_pdf': self.cp_pdf/self.cp_pdf.sum(),
            'consistency_rate':self.cp_pdf[0,0]/(self.cp_pdf.sum()),
            'common_prefix_cdf_k': self.cp_cdf_k/((self.miner_num-self.adversary.get_adver_num())*self.total_round)
        })
        # Chain Quality Property
        cq_dict_prp, _ = chain_quality(self.global_chain_prp)
        honest_blocks_total = cq_dict_prp['Honest Block']  # 假设cq_dict中诚实矿工产生的块的数量用'honest'键
        adversarial_blocks_total = cq_dict_prp['Adversary Block']  # 假设cq_dict中敌对矿工产生的块的数量用'adversarial'键
        for vt_chain in self.global_vt_chains:
            cq_dict_vt, _ = chain_quality(vt_chain)
            honest_blocks_total += cq_dict_vt['Honest Block']
            adversarial_blocks_total += cq_dict_vt['Adversary Block']
        chain_quality_property = honest_blocks_total / (honest_blocks_total + adversarial_blocks_total)
        cq_dict = {
            "Honest": honest_blocks_total,
            "Adver": adversarial_blocks_total
        }

        total_stats.update({
            'chain_quality_property': cq_dict,
            'ratio_of_blocks_contributed_by_malicious_players': round(chain_quality_property, 5),
            'upper_bound t/(n-t)': round(
                self.adversary.get_adver_num() / (self.miner_num - self.adversary.get_adver_num()), 5)
        })
        # Network Property
        total_stats.update({'block_propagation_times': {} })
        if not isinstance(self.network,network.SynchronousNetwork):
            self.network: network.BoundedDelayNetwork
            ave_block_propagation_times = self.network.cal_block_propagation_times()
            total_stats.update({
                'block_propagation_times': ave_block_propagation_times
            })

        for k,v in total_stats.items():
            if type(v) is float:
                total_stats.update({k:round(v,8)})

        # show the results in the terminal
        # Chain Growth Property
        print('Chain Growth Property:')
        print(total_stats["num_of_generated_blocks"], "blocks are generated in",
              self.total_round, "rounds, in which", total_stats["num_of_stale_blocks"], "are stale blocks.")
        print("Average chain growth in honest miners' chain:", round(growth, 3))
        print("Number of Forks:", total_stats["num_of_forks"])
        print("Fork rate:", total_stats["fork_rate"])
        print("Stale rate:", total_stats["stale_rate"])
        print("Average block time (main chain):", total_stats["average_block_time_main"], "rounds/block")
        print("Block throughput (main chain):", total_stats["block_throughput_main"], "blocks/round")
        print("Throughput in MB (main chain):", total_stats["throughput_main_MB"], "MB/round")
        print("Average block time (total):", total_stats["average_block_time_total"], "rounds/block")
        print("Block throughput (total):", total_stats["block_throughput_total"], "blocks/round")
        print("Throughput in MB (total):", total_stats["throughput_total_MB"], "MB/round")
        print("")
        # Common Prefix Property
        print('Common Prefix Property:')
        print('The common prefix pdf:')
        print(self.cp_pdf/self.cp_pdf.sum())
        print('Consistency rate:',self.cp_pdf[0,0]/(self.cp_pdf.sum()))
        #print('The common prefix cdf with respect to k:')
        #print(self.cp_cdf_k / ((self.miner_num - self.max_adversary) * self.total_round))
        print("")
        # Chain Quality Property
        print('Chain_Quality Property:', cq_dict)
        print('Ratio of blocks contributed by malicious players:', chain_quality_property)
        txpool = global_var.get_txpool()
        print('TXPOOL:', txpool)
        # Attack Property
        if self.adversary.get_info():
            print('The simulation data of', self.adversary.get_attack_type_name() , 'is as follows', ':\n', self.adversary.get_info())
        # Network Property
        if not isinstance(self.network,network.SynchronousNetwork):
            print('Block propagation times:', ave_block_propagation_times)

        return total_stats

    def view_and_write(self):
        # stats = self.view()
        #
        # self.global_chain_prp.printchain2txt()
        #
        # # save the results in the evaluation results.txt
        # RESULT_PATH = global_var.get_result_path()
        # with open(RESULT_PATH / 'evaluation results.txt', 'a+',  encoding='utf-8') as f:
        #     blocks_round = ['block_throughput_main', 'block_throughput_total']
        #     MB_round = ['throughput_main_MB', 'throughput_total_MB']
        #     rounds_block = ['average_block_time_main', 'average_block_time_total']
        #
        #     for k,v in stats.items():
        #         if k in blocks_round:
        #             print(f'{k}: {v} blocks/round', file=f)
        #         elif k in MB_round:
        #             print(f'{k}: {v} MB/round', file=f)
        #         elif k in rounds_block:
        #             print(f'{k}: {v} rounds/block', file=f)
        #         else:
        #             print(f'{k}: {v}', file=f)
        #
        # if global_var.get_compact_outputfile():
        #     return stats
        #
        # # save local chain for all miners
        # for miner in self.miners:
        #     miner.consensus.local_chain_prp.printchain2txt(f"chain_data{str(miner.miner_id)}.txt")
        #     for i in range(global_var.get_vtnum()):
        #         miner.consensus.local_chain_vt[i].printchain2txt(f"chain_data{str(miner.miner_id)}.txt")
        #
        # # Show or save figures for global_chain_prp
        # self.global_chain_prp.ShowStructure(miner_num=self.miner_num, new_figure=True, color='b', marker='o')
        #
        # # In the same figure, plot other chains (global_vt_chains)
        # for i in range(global_var.get_vtnum()):
        #     self.global_vt_chains[i].ShowStructure(miner_num=self.miner_num, new_figure=False, color='g', marker='v')
        #
        # RESULT_PATH = global_var.get_result_path()
        # plt.savefig(RESULT_PATH / 'blockchain_visualization_combined.svg')
        # if global_var.get_show_fig():
        #     plt.show()
        # plt.close()
        #
        # # Block interval distribution
        # self.miners[0].consensus.local_chain_prp.GetBlockIntervalDistribution()

        vote_counts = global_var.get_vtcount()

        max_votes_per_height = {}
        for block in self.global_chain_prp:
            if block.height not in max_votes_per_height or \
                    vote_counts.get(block.name, 0) > vote_counts.get(max_votes_per_height[block.height].name, 0) or \
                    (vote_counts.get(block.name, 0) == vote_counts.get(max_votes_per_height[block.height].name,
                                                                       0) and block.blockhash < max_votes_per_height[
                         block.height].blockhash):
                max_votes_per_height[block.height] = block

        # Visualize proposer chain with vote counts
        dot = self.global_chain_prp.ShowStructureWithGraphviz(dot=None, chain_id='prpchain', prpchain=None,
                                                              vote_counts=vote_counts,
                                                              max_votes_per_height=max_votes_per_height)

        # Visualize each voter chain
        for i in range(global_var.get_vtnum()):
            dot = self.global_vt_chains[i].ShowStructureWithGraphviz(dot=dot, chain_id=f'vtchain_{i}', prpchain=None)

        # Render final graph
        dot.render(directory=global_var.get_result_path() / "blockchain_visualization", format='svg',
                   view=global_var.get_show_fig())

        # Generate routing graph from JSON if network is TopologyNetwork
        if isinstance(self.network, network.TopologyNetwork):
            self.network.gen_routing_gragh_from_json()

        # return stats

    def process_bar(self,process,total,t_0,unit='round/s'):
        bar_len = 50
        percent = (process)/total
        cplt = "■" * math.ceil(percent*bar_len)
        uncplt = "□" * (bar_len - math.ceil(percent*bar_len))
        time_len = time.time()-t_0+0.0000000001
        time_cost = time.gmtime(time_len)
        vel = process/(time_len)
        time_eval = time.gmtime(total/(vel+0.001))#Events: see events.log
        print("\r{}{}  {:.5f}%  {}/{}  {:.2f} {}  {}:{}:{}>>{}:{}:{}  "\
        .format(cplt, uncplt, percent*100, process, total, vel, unit, time_cost.tm_hour, time_cost.tm_min, time_cost.tm_sec,\
            time_eval.tm_hour, time_eval.tm_min, time_eval.tm_sec),end="", flush=True)
        return vel


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    times_prob = {0:0, 0.03: 0.944, 0.05: 1.804, 0.08: 2.767, 0.1: 3.308, 0.2: 5.421,
              0.4: 8.797, 0.5: 10.396, 0.6: 12.071, 0.7: 13.956, 0.8: 16.217, 0.9: 19.377,
              0.93: 20.777, 0.95: 21.971, 0.98: 24.683, 1.0: 29.027}
    times_vec ={0:0, 0.1: 1, 0.2: 2, 0.3:3, 0.4: 4, 0.5: 5.0, 0.6: 6.0, 0.7: 7.0, 0.8: 8.0, 0.9: 9.0, 1.0: 10}


    times_tp = {0:0, 0.03: 9.297, 0.05: 12.257, 0.08: 15.889, 0.1: 17.185, 0.2: 21.459, 0.4: 26.592, 0.5: 28.493, 0.6: 30.343, 0.7: 32.232, 0.8: 34.231, 0.9: 36.993, 0.93: 38.194, 0.95: 39.256, 0.98: 41.946, 1.0: 46.706}
    times_outage = {0:0, 0.03: 9.627, 0.05: 12.988, 0.08: 16.45, 0.1: 17.94, 0.2: 22.193, 0.4: 27.405, 0.5: 29.353, 0.6: 31.262, 0.7: 33.265, 0.8: 35.496, 0.9: 38.663, 0.93: 40.298, 0.95: 41.889, 0.98: 45.681, 1.0: 52.662}
    times_wo_parition = {0:0,  0.05: 21.713, 0.08: 27.103, 0.1: 29.326, 0.2: 42.763, 0.4: 61.751, 0.5: 68.969, 0.6: 80.483, 0.8: 92.329, 0.9: 103.141, 0.93: 107.383, 0.95: 110.757, 0.98: 119.123, 1.0: 145.109}
    times_dynamic ={0:0, 0.03: 18.237, 0.05: 24.153, 0.08: 30.627, 0.1: 34.757, 0.2: 56.545, 0.4: 81.044, 0.5: 84.115, 0.6: 103.68, 0.7: 128.212, 0.8: 147.1, 0.9: 196.187, 0.93: 238.383, 0.95: 360.152, 0.98: 2226.653, 1.0: 3848.5}
    rcv_rates = list(times_tp.keys())
    t = list(times_tp.values())
    t = [tt/t[-1] for tt in t]
    plt.plot(t,rcv_rates,"--o", label= "Topology Network")

    rcv_rates = list(times_outage.keys())
    t = list(times_outage.values())
    t = [tt/t[-1] for tt in t]
    plt.plot(t,rcv_rates,"--o", label= "Topology Network + Link Outage")

    rcv_rates = list(times_wo_parition.keys())
    t = list(times_wo_parition.values())
    t = [tt/t[-1] for tt in t]
    plt.plot(t,rcv_rates,"--o", label= "Topology Network + Dynamic")

    rcv_rates = list(times_dynamic.keys())
    t = list(times_dynamic.values())
    t = [tt/t[-1] for tt in t]
    plt.plot(t,rcv_rates,"--o", label= "Topology Network + Dynamic + 3Patitions")

    rcv_rates = list(times_prob.keys())
    t = list(times_prob.values())
    t = [tt/t[-1] for tt in t]
    plt.plot(t,rcv_rates,"--^", label= "Stochastic Propagation Network")
    rcv_rates = list(times_vec.keys())
    t = list(times_vec.values())
    t = [tt/t[-1] for tt in t]
    plt.plot(t,rcv_rates,"--*", label= "Deterministic Propagation Network")
    plt.xlabel("Normalized number of rounds passed")
    plt.ylabel("Ratio of received miners")
    plt.legend()
    plt.grid()
    plt.show()