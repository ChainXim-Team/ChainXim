import time
import math
import copy
import random
from typing import List
import numpy as np

import global_var
import network
from chain import Chain,Block
from miner import Miner
from Attack import default_attack_mode
from functions import for_name
from external import common_prefix, chain_quality, chain_growth


class Environment(object):

    def __init__(self,  t:int = None, adversary_ids:tuple = None,
                 consensus_param:dict = None, network_param:dict = None, 
                 genesis_blockheadextra:dict = None, genesis_blockextra:dict = None):
        '''initiate the running environment

        Param
        -----
        t: maximum number of miners(int)
        adversary_ids: The IDs of adverary members (tuple)
        consensus_param: consensus parameters (dict)
        network_param: network parameters (dict)
        genesis_blockheadextra: initialize variables in the head of genesis block (dict)
        genesis_blockextra: initialize variables in the genesis block (dict)
        
        '''
        #environment parameters
        self.miner_num = global_var.get_miner_num()  # number of miners
        self.total_round = 0
        # configure extra genesis block info
        consensus_type = for_name(global_var.get_consensus_type())
        consensus_type.genesis_blockheadextra = genesis_blockheadextra
        consensus_type.genesis_blockextra = genesis_blockextra
        # generate miners
        self.miners:List[Miner] = []
        for miner_id in range(self.miner_num):
            self.miners.append(Miner(miner_id, consensus_param))
        self.envir_create_global_chain()
        # evaluation
        self.max_suffix = 10
        self.cp_pdf = np.zeros((1, self.max_suffix)) # 每轮结束时，各个矿工的链与common prefix相差区块个数的分布
        self.cp_cdf_k = np.zeros((1, self.max_suffix))  # 每轮结束时，把主链减少k个区块，是否被包含在矿工的区块链里面
        
        # select adversay
        self.max_adversary = t  # maximum number of adversary
        self.adversary_mem:List[Miner] = []
        if adversary_ids is not None:
            if len(adversary_ids) != self.max_adversary:
                self.max_adversary = len(adversary_ids)
            self.select_adversary(*adversary_ids)
        elif self.max_adversary > 0:
            self.select_adversary_random()
            adversary_ids = [adversary.Miner_ID for adversary in self.adversary_mem]
        # generate network
        self.network:network.Network = for_name(global_var.get_network_type())(self.miners)
        self.network.set_net_param(**network_param)
        ## 初始化攻击模组
        if self.adversary_mem: # 如果有攻击者，则创建攻击实例
            self.attack = default_attack_mode(self.adversary_mem, self.global_chain, self.network)
            self.adverflag = random.randint(1,len(self.adversary_mem))
        self.attack_execute_type = global_var.get_attack_execute_type()
        
        # add a line in chain data to distinguish adversaries from non-adversaries
        CHAIN_DATA_PATH=global_var.get_chain_data_path()
        for miner in self.miners:
            with open(CHAIN_DATA_PATH / f'chain_data{str(miner.Miner_ID)}.txt','a') as f:
                print(f"isAdversary: {miner.isAdversary}\n", file=f)
        parameter_str = 'Parameters:\n' + \
            f'Miner Number: {self.miner_num} \n' + \
            f'Adversary Miners: {adversary_ids} \n' + \
            f'Consensus Protocol: {consensus_type.__name__} \n' + \
            f'Network Type: {type(self.network).__name__} \n' + \
            f'Network Param:  {network_param} \n' + \
            f'Consensus Param: {consensus_param} \n'
        if self.adversary_mem:
            parameter_str += f'Attack Execute Type: {self.attack_execute_type} \n'
        print(parameter_str)
        with open(global_var.get_result_path() / 'parameters.txt', 'w+') as conf:
            print(parameter_str, file=conf)

    def select_adversary_random(self):
        '''
        随机选择对手
        return:self.adversary_mem
        '''
        self.adversary_mem=random.sample(self.miners,self.max_adversary)
        for adversary in self.adversary_mem:
            adversary.set_adversary(True)
        return self.adversary_mem

    def select_adversary(self,*Miner_ID):

        for miner in Miner_ID:
            self.adversary_mem.append(self.miners[miner])
            self.miners[miner].set_adversary(True)
        return self.adversary_mem
     
    '''
    def clear_adversary(self):

        for adversary in self.adversary_mem:
            adversary.set_adversary(False)
        self.adversary_mem=[]
    '''

    def envir_create_global_chain(self):
        '''create global chain and its genesis block by copying local chain from the first miner.'''
        self.global_chain = Chain()
        self.global_chain.head = copy.deepcopy(self.miners[0].consensus.Blockchain.head)
        self.global_chain.lastblock = self.global_chain.head

    def attack_execute(self,round):
        if self.attack_execute_type == 'execute_sample0':
            self.attack.execute_sample0(round)
        elif self.attack_execute_type == 'execute_sample1':
            self.attack.execute_sample1(round)

        
    def exec(self, num_rounds, max_height, process_bar_type):

        '''
        调用当前miner的BackboneProtocol完成mining
        当前miner用add_block_direct添加上链
        之后gobal_chain用深拷贝的add_block_copy上链
        '''
        if process_bar_type != 'round' and process_bar_type != 'height':
            raise ValueError('process_bar_type should be \'round\' or \'height\'')
        ## 开始循环
        t_0 = time.time() # 记录起始时间
        cached_height = self.global_chain.lastblock.BlockHeight()
        for round in range(1, num_rounds+1):
            inputfromz = round # 生成输入

            adver_tmpflag = 1    
            for temp_miner in self.miners:
                if temp_miner.isAdversary:
                    temp_miner.input_tape.append(("INSERT", inputfromz))
                    if adver_tmpflag == self.adverflag:
                        self.attack_execute(round)
                        adver_tmpflag = adver_tmpflag + 1
                    else:
                        adver_tmpflag = adver_tmpflag + 1

                else:
                    ## 处理诚实矿工
                    temp_miner.input_tape.append(("INSERT", inputfromz))
                    # run backbone protocol
                    if (new_msgs := temp_miner.BackboneProtocol(round)) is not None:
                        self.network.access_network(new_msgs,temp_miner.Miner_ID,round)
                        for msg in new_msgs:
                            if isinstance(msg, Block):
                                self.global_chain.add_block_copy(msg)
                    temp_miner.input_tape = []  # clear the input tape
                    temp_miner.consensus.receive_tape = []  # clear the communication tape
                    ##

            self.network.diffuse(round)  # diffuse(C)
            #self.assess_common_prefix()
            #self.assess_common_prefix_k() # TODO 放到view(),评估独立于仿真过程
            # 分割一下
        # self.clear_adversary()
            if self.adversary_mem and not global_var.get_compact_outputfile():
                self.attack.attacklog2txt(round)
        
            # 全局链高度超过max_height之后就提前停止
            current_height = self.global_chain.lastblock.BlockHeight()
            if current_height > max_height:
                break
            # 根据process_bar_type决定进度条的显示方式
            if process_bar_type == 'round':
                self.process_bar(round, num_rounds, t_0, 'round/s')
            elif current_height > cached_height and process_bar_type == 'height':
                cached_height = current_height
                self.process_bar(current_height, max_height, t_0, 'block/s')
        self.total_round = self.total_round + round
        if self.adversary_mem:
            self.attack.resultlog2txt()
        
        
    def assess_common_prefix(self):
        # Common Prefix Property
        cp = self.miners[0].consensus.Blockchain.lastblock
        for i in range(1, self.miner_num):
            if not self.miners[i].isAdversary:
                cp = common_prefix(cp, self.miners[i].consensus.Blockchain)
        len_cp = cp.height
        for i in range(0, self.miner_num):
            len_suffix = self.miners[0].consensus.Blockchain.lastblock.height - len_cp
            if len_suffix >= 0 and len_suffix < self.max_suffix:
                self.cp_pdf[0, len_suffix] = self.cp_pdf[0, len_suffix] + 1
    def assess_common_prefix_k(self):
        # 一种新的计算common prefix的方法
        # 每轮结束后，砍掉主链后
        cp_k = self.global_chain.lastblock
        cp_stat = np.zeros((1, self.miner_num))
        for k in range(self.max_suffix):
            if cp_k is None or np.sum(cp_stat) == self.miner_num-self.max_adversary:  # 当所有矿工的链都达标后，后面的都不用算了，降低计算复杂度
                self.cp_cdf_k[0, k] += self.miner_num-self.max_adversary
                continue
            cp_stat = np.zeros((1, self.miner_num))  # 用来统计哪些矿工的链已经达标，
            cp_sum_k = 0
            for i in range(self.miner_num):
                if not self.miners[i].isAdversary:
                    if cp_stat[0, i] == 1:
                        cp_sum_k += 1
                    else:
                        if cp_k == common_prefix(cp_k, self.miners[i].consensus.Blockchain):
                            cp_stat[0, i] = 1
                            cp_sum_k += 1
            self.cp_cdf_k[0, k] += cp_sum_k
            cp_k = cp_k.last

    def view(self) -> dict:
        # 展示一些仿真结果
        print('\n')
        print("Global Tree Structure:", "")
        self.global_chain.ShowStructure1()
        print("End of Global Tree", "")

        # Evaluation Results
        stats = self.global_chain.CalculateStatistics(self.total_round)
        stats.update({'total_round':self.total_round})
        # Chain Growth Property
        growth = 0
        num_honest = 0
        for i in range(self.miner_num):
            if not self.miners[i].isAdversary:
                growth = growth + chain_growth(self.miners[i].consensus.Blockchain)
                num_honest = num_honest + 1
        growth = growth / num_honest
        stats.update({
            'average_chain_growth_in_honest_miners\'_chain': growth
        })
        # Common Prefix Property
        #stats.update({
        #    'common_prefix_pdf': self.cp_pdf/self.cp_pdf.sum(),
        #    'consistency_rate':self.cp_pdf[0,0]/(self.cp_pdf.sum()),
        #    'common_prefix_cdf_k': self.cp_cdf_k/((self.miner_num-self.max_adversary)*self.total_round)
        #})
        # Chain Quality Property
        cq_dict, chain_quality_property = chain_quality(self.global_chain)
        stats.update({
            'chain_quality_property': cq_dict,
            'ratio_of_blocks_contributed_by_malicious_players': round(chain_quality_property, 5),
            'upper_bound t/(n-t)': round(self.max_adversary / (self.miner_num - self.max_adversary), 5)
        })
        # Network Property
        stats.update({'block_propagation_times': {} })
        if not isinstance(self.network,network.SynchronousNetwork):
            ave_block_propagation_times = self.network.cal_block_propagation_times()
            stats.update({
                'block_propagation_times': ave_block_propagation_times
            })
        
        for k,v in stats.items():
            if type(v) is float:
                stats.update({k:round(v,8)})

        # show the results in the terminal
        # Chain Growth Property
        print('Chain Growth Property:')
        print(stats["num_of_generated_blocks"], "blocks are generated in",
              self.total_round, "rounds, in which", stats["num_of_stale_blocks"], "are stale blocks.")
        print("Average chain growth in honest miners' chain:", round(growth, 3))
        print("Number of Forks:", stats["num_of_forks"])
        print("Fork rate:", stats["fork_rate"])
        print("Stale rate:", stats["stale_rate"])
        print("Average block time (main chain):", stats["average_block_time_main"], "rounds/block")
        print("Block throughput (main chain):", stats["block_throughput_main"], "blocks/round")
        print("Throughput in MB (main chain):", stats["throughput_main_MB"], "MB/round")
        print("Average block time (total):", stats["average_block_time_total"], "rounds/block")
        print("Block throughput (total):", stats["block_throughput_total"], "blocks/round")
        print("Throughput in MB (total):", stats["throughput_total_MB"], "MB/round")
        print("")
        # Common Prefix Property
        #print('Common Prefix Property:')
        #print('The common prefix pdf:')
        #print(self.cp_pdf/self.cp_pdf.sum())
        #print('Consistency rate:',self.cp_pdf[0,0]/(self.cp_pdf.sum()))
        #print('The common prefix cdf with respect to k:')
        #print(self.cp_cdf_k / ((self.miner_num - self.max_adversary) * self.total_round))
        print("")
        # Chain Quality Property
        print('Chain_Quality Property:', cq_dict)
        print('Ratio of blocks contributed by malicious players:', chain_quality_property)
        print('Upper Bound t/(n-t):', self.max_adversary / (self.miner_num - self.max_adversary))
        # Network Property
        if not isinstance(self.network,network.SynchronousNetwork):
            print('Block propagation times:', ave_block_propagation_times)

        return stats

    def view_and_write(self):
        stats = self.view()
        self.global_chain.printchain2txt()

        # save the results in the evaluation results.txt
        RESULT_PATH = global_var.get_result_path()
        with open(RESULT_PATH / 'evaluation results.txt', 'a+',  encoding='utf-8') as f:
            blocks_round = ['block_throughput_main', 'block_throughput_total']
            MB_round = ['throughput_main_MB', 'throughput_total_MB']
            rounds_block = ['average_block_time_main', 'average_block_time_total']

            for k,v in stats.items():
                if k in blocks_round:
                    print(f'{k}: {v} blocks/round', file=f)
                elif k in MB_round:
                    print(f'{k}: {v} MB/round', file=f)
                elif k in rounds_block:
                    print(f'{k}: {v} rounds/block', file=f)
                else:
                    print(f'{k}: {v}', file=f)

        if global_var.get_compact_outputfile():
            return stats

        # save local chain for all miners
        for miner in self.miners:
            miner.consensus.Blockchain.printchain2txt(f"chain_data{str(miner.Miner_ID)}.txt")

        # show or save figures
        self.global_chain.ShowStructure(self.miner_num)
        # block interval distribution
        self.miners[0].consensus.Blockchain.get_block_interval_distribution()

        self.global_chain.ShowStructureWithGraphviz()

        if self.network.__class__.__name__=='TopologyNetwork':
            self.network.gen_routing_gragh_from_json()

        return stats

    def process_bar(self,process,total,t_0,unit='round/s'):
        bar_len = 50
        percent = (process)/total
        cplt = "■" * math.ceil(percent*bar_len)
        uncplt = "□" * (bar_len - math.ceil(percent*bar_len))
        time_len = time.time()-t_0+0.0000000001
        time_cost = time.gmtime(time_len)
        vel = process/(time_len)
        time_eval = time.gmtime(total/(vel+0.001))
        print("\r{}{}  {:.5f}%  {}/{}  {:.2f} {}  {}:{}:{}>>{}:{}:{}  Events: see events.log "\
        .format(cplt, uncplt, percent*100, process, total, vel, unit, time_cost.tm_hour, time_cost.tm_min, time_cost.tm_sec,\
            time_eval.tm_hour, time_eval.tm_min, time_eval.tm_sec),end="", flush=True)
