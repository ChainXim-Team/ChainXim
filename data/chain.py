import copy
import logging
from collections import defaultdict

import graphviz
import matplotlib.pyplot as plt

import global_var

from .block import Block
from functions import INT_LEN, BYTE_ORDER

logger = logging.getLogger(__name__)

class Chain(object):

    def __init__(self, miner_id = None):
        self.miner_id = miner_id
        self.head = None
        self.last_block = self.head  # 指向最新区块，代表矿工认定的主链
        self.block_set = defaultdict(Block)
        self.switch_tracker_callback = None # 用于记录链尾切换事件
        # self.merge_tracker_callback = None # 用于记录区块并入事件
        self.merge_callback = None # 用于在Environment处理区块并入事件
        '''
        默认的共识机制中会对chain添加一个创世区块
        默认情况下chain不可能为空
        '''

    def __getstate__(self):
        chain = copy.deepcopy(self)
        for block in chain.block_set.values():
            block.parentblock = None
            block.next = [block.blockhash for block in block.next]
        chain.switch_tracker_callback = None
        # chain.merge_tracker_callback = None
        chain.last_block = self.last_block.blockhash
        return vars(chain)

    def __setstate__(self, state):
        self.__dict__.update(state)
        for block in self.block_set.values():
            if block.height != 0:
                block.parentblock = self.block_set[block.blockhead.prehash]
            block.next = [self.block_set[hash] for hash in block.next]
        self.last_block = self.block_set[self.last_block]

    def __deepcopy__(self, memo):
        if self.head is None:
            return None
        copy_chain = Chain(miner_id=self.miner_id)
        copy_chain.head = copy.deepcopy(self.head)
        copy_chain.block_set[copy_chain.head.blockhash] = copy_chain.head
        memo[id(copy_chain.head)] = copy_chain.head
        q = [copy_chain.head]
        q_o = [self.head]
        copy_chain.last_block = copy_chain.head
        while q_o:
            for block in q_o[0].next:
                copy_block = copy.deepcopy(block, memo)
                copy_block.parentblock = q[0]
                q[0].next.append(copy_block)
                q.append(copy_block)
                q_o.append(block)
                memo[id(copy_block)] = copy_block
                copy_chain.block_set[copy_block.blockhash] = copy_block
                if block.name == self.last_block.name:
                    copy_chain.last_block = copy_block
            q.pop(0)
            q_o.pop(0)
        return copy_chain
    
    def __is_empty(self):
        if self.head is None:
            # print("Chain Is empty")
            return True
        else:
            return False

    ## chain数据层主要功能区↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓

    def search_block_by_hash(self, blockhash: bytes=None):
        # 利用区块哈希，搜索某块是否存在(搜索树)
        # 存在返回区块地址，不存在返回None
        return self.block_set.get(blockhash, None)

    def search_block(self, block: Block):
        # 利用区块哈希，搜索某块是否存在(搜索树)
        # 存在返回区块地址，不存在返回None
        if self.head is None or block is None:
            return None
        else:
            return self.block_set.get(block.blockhash)

    def get_last_block(self):  # 返回最深的block，空链返回None
        return self.last_block

    def set_last_block(self,block:Block):
        # 设置本链最深的块
        # 本块必须是在链中的
        if self.search_block(block):
            self.last_block = block
            if self.switch_tracker_callback:
                self.switch_tracker_callback(block)
        else:
            return

    def get_height(self,block:Block=None):
        # 默认返回最深区块的高度
        # 或者返回指定区块的高度
        if block is not None:
            return block.get_height()
        else:
            return self.get_last_block().get_height()

    def add_blocks(self, blocks: Block | list[Block], insert_point:Block=None):
        if blocks == None:
            return
        # 添加区块的功能 (深拷贝*)
        # item是待添加的内容 可以是list[Block]类型 也可以是Block类型
        # 即可以批量添加也可以只添加一个区块
        # 批量添加时blocks按顺序构成哈希链，第一个区块是最新区块
        # inset_point 是插入区块的位置 从其后开始添加 默认为最深链
        '''
        添加区块的功能不会考虑区块前后的hash是否一致
        这个任务不属于数据层 是共识层的任务
        数据层只负责添加
        '''
        add_block_list:list[Block]=[]
        if insert_point is None:
            if isinstance(blocks,Block):
                insert_point = self.search_block_by_hash(blocks.blockhead.prehash)
            else:
                insert_point = self.search_block_by_hash(blocks[-1].blockhead.prehash)
            assert self.__is_empty() or insert_point is not None

        if isinstance(blocks,Block):
            if (cur2add := self.search_block(blocks)) is not None:
                return cur2add
            add_block_list.append(copy.deepcopy(blocks))
        else:
            checklist = copy.copy(blocks)
            while checklist:
                cur2add = checklist.pop()
                # 寻找第一个不在链中的区块
                if (local_block := self.search_block(cur2add)) is not None:
                    insert_point = local_block
                else:
                    checklist.append(cur2add)
                    break
            add_block_list.extend(copy.deepcopy(checklist))

        # 处理特殊情况
            # 如果当前区块为空 添加blocklist的第一个区块
            # 默认这个特殊情况是不会被触发的
            # 只有consens里的创世区块会触发 其他情况无视
        if self.__is_empty():
            self.head = add_block_list.pop()
            self.block_set[self.head.blockhash] = self.head
            self.set_last_block(self.head)
        cur2add = self.head

        while add_block_list:
            cur2add = add_block_list.pop() # 提取当前待添加区块list中的一个
            cur2add.parentblock = insert_point # 设置它的父节点
            insert_point.next.append(cur2add)  # 设置父节点的子节点
            cur2add.next = []            # 初始化它的子节点
            insert_point = cur2add             # 父节点设置为它
            self.block_set[cur2add.blockhash] = cur2add # 将它加入blockset中

        if self.merge_callback:
            self.merge_callback(cur2add)

        # if self.merge_tracker_callback:
        #     self.merge_tracker_callback(cur2add)

        # 如果新加的区块的高度比现在的链的高度高 重新将lastblock指向新加区块
        if cur2add.get_height() > self.get_height():
            self.set_last_block(cur2add)
        return cur2add

    def add_block_forcibly(self, block: Block):
        # 该功能是强制将该区块加入某条链 一般不被使用与共识中
        # 返回值：深拷贝插入完之后新插入链的块头
        # block 的 last必须不为none
        # 不会为block默认赋值 要求使用该方法必须给出添加的区块 否则提示报错

        copylist:list[Block] = []  # 需要拷贝过去的区块list
        local_tmp = self.search_block(block)
        while block and not local_tmp:
            copylist.append(block)
            block = block.parentblock
            local_tmp = self.search_block(block)

        newest_block = None
        if local_tmp:
            newest_block = self.add_blocks(blocks=copylist,insert_point=local_tmp)
        return newest_block  # 返回被添加到链中的、入参block深拷贝后的新区块，如果block的祖先区块不在链中则返回None

    def delete_block(self,block:Block=None):
        '''
        没有地方被使用
        就先不管了
        可能的使用场景：
        矿工不需要记录自身的区块链视野 可以只记录主链
        需要删除分叉
        '''
        pass
    ## chain数据层主要功能区↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
        


    ## chain数据层外部方法区↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
        # 主要用于计算 展示链的相关数据
    def ShowBlock(self):  # 按从上到下从左到右展示block,打印块名
        if not self.head:
            print()
        q = [self.head]
        blocklist = []
        while q:
            block = q.pop(0)
            blocklist.append(block)
            print("{};".format(block.name), end="")
            for i in block.next:
                q.append(i)
        print("")
        return blocklist

    def InversShowBlock(self):
        # 返回逆序的主链
        cur = self.get_last_block()
        blocklist = []
        while cur:
            # print(cur.name)
            blocklist.append(cur)
            cur = cur.parentblock
        return blocklist

    def ShowLChain(self):
        # 打印主链
        blocklist = self.InversShowBlock()
        blocklist.reverse()
        for i in blocklist:
            print("{}→→→→".format(i.name), end="")
        print("")
        return blocklist

    def ShowStructure1(self):
        # 打印树状结构
        blocklist = [self.head]
        printnum = 1
        while blocklist:
            length = 0
            print("|    ", end="")
            print("-|   " * (printnum - 1))
            while printnum > 0:
                blocklist.extend(blocklist[0].next)
                blockprint = blocklist.pop(0)
                length += len(blockprint.next)
                print("{}   ".format(blockprint.name), end="")
                printnum -= 1
            print("")
            printnum = length

    def ShowStructure(self, miner_num=10):
        # 打印树状结构
        # 可能需要miner数量 也许放在这里不是非常合适？
        plt.figure()
        plt.rcParams['font.size'] = 16
        plt.rcParams['font.family'] = 'Times New Roman'
        blocktmp = self.head
        fork_list = []
        while blocktmp:
            if blocktmp.isGenesis is False:
                rd2 = blocktmp.blockhead.timestamp + blocktmp.blockhead.miner / miner_num
                rd1 = blocktmp.parentblock.blockhead.timestamp + blocktmp.parentblock.blockhead.miner / miner_num
                ht2 = blocktmp.height
                ht1 = ht2 - 1
                if blocktmp.isAdversaryBlock:
                    plt.scatter(rd2, ht2, color='r', marker='o')
                    plt.plot([rd1, rd2], [ht1, ht2], color='r')
                else:
                    plt.scatter(rd2, ht2, color='b', marker='o')
                    plt.plot([rd1, rd2], [ht1, ht2], color='b')
            else:
                plt.scatter(0, 0, color='b', marker='o')
            list_tmp = copy.copy(blocktmp.next)
            if list_tmp:
                blocktmp = list_tmp.pop(0)
                fork_list.extend(list_tmp)
            else:
                if fork_list:
                    blocktmp = fork_list.pop(0)
                else:
                    blocktmp = None
        plt.xlabel('Round')
        plt.ylabel('Block Height')
        plt.grid(True)
        RESULT_PATH = global_var.get_result_path()
        plt.savefig(RESULT_PATH / 'blockchain visualisation.svg')
        if global_var.get_show_fig():
            plt.show()
        plt.close()

    def ShowStructureWithGraphviz(self,other_list:list[int] = None):
        '''借助Graphviz将区块链可视化'''
        # 采用有向图
        dot = graphviz.Digraph('Blockchain Structure',engine='dot')
        blocktmp = self.head
        fork_list = []
        while blocktmp:
            if blocktmp.isGenesis is False:
                # 建立区块节点
                if blocktmp.isAdversaryBlock:
                    dot.node(blocktmp.name, shape='rect', color='red')
                else:
                    if other_list is None:
                        dot.node(blocktmp.name,shape='rect',color='blue')
                    else:
                        dot.node(blocktmp.name,shape='rect',color='orange' if blocktmp.blockhead.miner in other_list else 'blue')
                # 建立区块连接
                dot.edge(blocktmp.parentblock.name, blocktmp.name)
            else:
                dot.node('B0',shape='rect',color='black',fontsize='20')
            list_tmp = copy.copy(blocktmp.next)
            if list_tmp:
                blocktmp = list_tmp.pop(0)
                fork_list.extend(list_tmp)
            else:
                if fork_list:
                    blocktmp = fork_list.pop(0)
                else:
                    blocktmp = None
        # 生成矢量图,展示结果
        dot.render(directory=global_var.get_result_path() / "blockchain_visualization",
                   format='svg', view=global_var.get_show_fig())

    def GetBlockIntervalDistribution(self):
        stat = []
        blocktmp2 = self.last_block
        height = blocktmp2.height
        while not blocktmp2.isGenesis:
            blocktmp1 = blocktmp2.parentblock
            stat.append(blocktmp2.blockhead.timestamp - blocktmp1.blockhead.timestamp)
            blocktmp2 = blocktmp1
        if height <= 1000:
            bins = 10
        else:
            bins = 20
        plt.rcParams['font.size'] = 16
        plt.rcParams['font.family'] = 'Times New Roman'
        plt.hist(stat, bins=bins, histtype='bar', range=(0, max(stat)))
        plt.xlabel('Rounds')
        plt.ylabel('Times')
        # plt.title('Block generation interval distribution')
        RESULT_PATH = global_var.get_result_path()
        plt.savefig(RESULT_PATH / 'block_interval_distribution.svg')
        if global_var.get_show_fig():
            plt.show()
        plt.close()
    
    def printchain2txt(self, chain_data_url='chain_data.txt'):
        '''
        前向遍历打印链中所有块到文件
        param:
            chain_data_url:打印文件位置,默认'chain_data.txt'
        '''
        def save_chain_structure(chain,f):
            blocklist = [chain.head]
            printnum = 1
            while blocklist:
                length = 0
                print("|    ", end="",file=f)
                print("-|   " * (printnum - 1),file=f)
                while printnum > 0:
                    blocklist.extend(blocklist[0].next)
                    blockprint = blocklist.pop(0)
                    length += len(blockprint.next)
                    print("{}   ".format(blockprint.name), end="",file=f)
                    printnum -= 1
                print("",file=f)
                printnum = length

        CHAIN_DATA_PATH=global_var.get_chain_data_path()
        if not self.head:
            with open(CHAIN_DATA_PATH / chain_data_url,'a') as f:
                print("empty chain",file=f)
            return
        
        with open(CHAIN_DATA_PATH /chain_data_url,'a') as f:
            print("Blockchain maintained BY Miner",self.miner_id,file=f)
            # 打印主链
            save_chain_structure(self,f)
            #打印链信息
            q:list[Block] = [self.head]
            blocklist = []
            while q:
                block = q.pop(0)
                blocklist.append(block)
                print(block,file=f)
                for i in block.next:
                    q.append(i)


    def CalculateStatistics(self, rounds, honest_miners: list, confirm_delay: int, dataitem_params: dict, valid_dataitems: set):
        # 统计一些数据
        stats = {
            "num_of_generated_blocks": -1,
            "height_of_longest_chain": 0,
            "num_of_valid_blocks": 0,
            "num_of_stale_blocks": 0,
            "stale_rate": 0,
            "num_of_forks": 0,
            "num_of_heights_with_fork":0,
            "fork_rate": 0,
            "average_block_time_main": 0,
            "block_throughput_main": 0,
            "throughput_main_MB": 0,
            "average_block_time_total": 0,
            "block_throughput_total": 0,
            "throughput_total_MB": 0,
            "double_spending_success_times": 0,
            # "double_spending_success_times_ver2": 0,
            "attack_fail": 0
        }
        q = [self.head]
        while q:
            stats["num_of_generated_blocks"] = stats["num_of_generated_blocks"] + 1
            blocktmp = q.pop(0)
            if blocktmp.height > stats["height_of_longest_chain"]:
                stats["height_of_longest_chain"] = blocktmp.height
            nextlist = blocktmp.next
            q.extend(nextlist)

        from external import common_prefix
        honest_cp = self.last_block
        honest_miner_ids = set()
        for miner in honest_miners:
            honest_miner_ids.add(miner.miner_id)
            honest_cp = common_prefix(honest_cp, miner.get_local_chain().get_last_block())
        stats["num_of_valid_blocks"] = honest_cp.height

        # Check the dataitems in the honest_cp
        from external import R
        valid_item_count = 0
        anomalous_item_count = 0
        if dataitem_params['dataitem_enable']:
            dataitem_set = set()
            dataitems_reversed = R(honest_cp)
            previous_item = int.from_bytes((255).to_bytes(1, BYTE_ORDER) * 2 * INT_LEN, BYTE_ORDER)
            for dataitem in dataitems_reversed:
                if dataitem.to_bytes(2*INT_LEN, BYTE_ORDER) in valid_dataitems:
                    if previous_item < dataitem and dataitem_params['dataitem_input_interval'] > 0:
                        anomalous_item_count += 1
                        logger.warning("A dataitem is out of order: %s", dataitem)
                    else:
                        valid_item_count += 1
                        previous_item = dataitem
                        if dataitem not in dataitem_set:
                            dataitem_set.add(dataitem)
                        else:
                            logger.warning("A dataitem duplicates")
                else:
                    anomalous_item_count += 1
            stats.update({
                'valid_dataitem_throughput': valid_item_count / rounds,
                'input_dataitem_rate': 1/dataitem_params['dataitem_input_interval'] \
                    if dataitem_params['dataitem_input_interval'] > 0 else valid_item_count / rounds
            })
            if stats['num_of_valid_blocks'] > 0:
                stats['block_average_size'] = \
                    (valid_item_count+anomalous_item_count) * dataitem_params['dataitem_size'] / stats['num_of_valid_blocks']
                stats['valid_dataitem_rate'] = valid_item_count / (valid_item_count + anomalous_item_count)
            else:
                stats['valid_dataitem_rate'] = 0
                stats['block_average_size'] = 0

        mainchain_block = set()
        current_block = honest_cp
        while current_block:
            mainchain_block.add(current_block.name)
            current_block = current_block.parentblock

        last_block_iter = honest_cp.parentblock
        while last_block_iter:
            stats["num_of_forks"] += len(last_block_iter.next) - 1
            stats["num_of_heights_with_fork"] += (len(last_block_iter.next) > 1)

            if len(last_block_iter.next) > 1:  # 发生分叉
                attacker_block_on_main = None
                # 1. 确认攻击者的区块在主链上
                for child_block in last_block_iter.next:
                    if child_block.blockhead.miner not in honest_miner_ids and \
                            child_block.name in mainchain_block:
                        attacker_block_on_main = child_block
                        break

                if attacker_block_on_main:
                    # 攻击者区块已在主链，现在检查是否有符合条件的被孤立分支
                    found_qualifying_orphaned_branch = False
                    for other_child_block in last_block_iter.next:
                        if other_child_block == attacker_block_on_main:
                            continue  # 跳过攻击者所在的主链分支

                        # 条件1: 被孤立分支的第一个块 (other_child_block) 需要是诚实块
                        if other_child_block.blockhead.miner in honest_miner_ids:  # 确保是被孤立的分支

                            # 条件2: 这个被孤立的分支长度需要大于等于 N
                            # DFS栈: (区块, 从other_child_block开始的当前路径长度)
                            dfs_stack = [(other_child_block, 1)]

                            # 记录这个孤立分支的最长路径
                            # 这个DFS只关心路径长度，不关心路径上后续块的诚实性
                            temp_longest_path_for_orphan = 0

                            while dfs_stack:
                                current_orphan_node, current_path_length = dfs_stack.pop()

                                if current_path_length > temp_longest_path_for_orphan:
                                    temp_longest_path_for_orphan = current_path_length

                                for next_orphan_node_candidate in current_orphan_node.next:
                                    dfs_stack.append((next_orphan_node_candidate, current_path_length + 1))

                            # 现在 temp_longest_path_for_orphan 是这条以诚实块开始的孤立分支的最长长度
                            if temp_longest_path_for_orphan >= confirm_delay:
                                found_qualifying_orphaned_branch = True
                                break  # 找到了一个符合条件的被孤立分支

                    if found_qualifying_orphaned_branch:
                        stats["double_spending_success_times"] += 1

            last_block_iter = last_block_iter.parentblock

        # # 第二种静态计算双花攻击成功的方法
        # last_block = honest_cp
        # attack_flag = False if last_block.blockhead.miner  in honest_miner_ids else True
        # last_block = honest_cp.parentblock
        # while last_block:
        #     if len(last_block.next) > 1 and attack_flag:
        #         attack_flag = False
        #         stats["double_spending_success_times_ver2"] += 1
        #     if last_block.blockhead.miner not in honest_miner_ids and not attack_flag:
        #         attack_flag = True
        #     last_block = last_block.parentblock

        stats["num_of_stale_blocks"] = stats["num_of_generated_blocks"] - stats["num_of_valid_blocks"]
        stats["average_block_time_main"] = rounds / stats["num_of_valid_blocks"] if stats["num_of_valid_blocks"] > 0 else -1
        stats["block_throughput_main"] = stats["num_of_valid_blocks"] / rounds
        blocksize = global_var.get_blocksize()
        stats["throughput_main_MB"] = blocksize * stats["block_throughput_main"]
        stats["average_block_time_total"] = rounds / stats["num_of_generated_blocks"]
        stats["block_throughput_total"] = 1 / stats["average_block_time_total"]
        stats["throughput_total_MB"] = blocksize * stats["block_throughput_total"]
        stats["fork_rate"] = stats["num_of_heights_with_fork"] / stats["num_of_valid_blocks"] if stats["num_of_valid_blocks"] > 0 else 0
        stats["stale_rate"] = stats["num_of_stale_blocks"] / stats["num_of_generated_blocks"]

        return stats
    
    def set_switch_tracker_callback(self, callback):
        self.switch_tracker_callback = callback

    def set_merge_tracker_callback(self, callback):
        self.merge_tracker_callback = callback

    def set_merge_callback(self, callback):
        self.merge_callback = callback

class LocalChainTracker(object):
    '''记录本地链每次切换lastblock的轮次以及lastblock的信息'''
    class ChainSwitchEvent(object):
        '''记录一次链尾切换的事件'''
        __slots__ = ['switch_round','name','blockhash','height','timestamp','subject']
        def __init__(self,switch_round:int,last_block:Block, subject:int):
            self.switch_round = switch_round
            self.name = last_block.name
            self.blockhash = last_block.blockhash
            self.height = last_block.height
            self.timestamp = last_block.blockhead.timestamp
            self.subject = subject # the miner who switches lastblock

    # class ChainMergeEvent(object):
    #     '''记录一次区块并入本地链的事件'''
    #     __slots__ = ['merge_round','name','blockhash','height','timestamp','subject']
    #     def __init__(self,merge_round:int,last_block:Block, subject:int):
    #         self.merge_round = merge_round
    #         self.name = last_block.name
    #         self.blockhash = last_block.blockhash
    #         self.height = last_block.height
    #         self.timestamp = last_block.blockhead.timestamp
    #         self.subject = subject # the miner who switches lastblock

    def __init__(self):
        self.chain_switch_events = []
        # self.block_merge_round = dict()
        self.current_round = 0
        
    def get_switch_tracker(self, miner_id:int):
        def tracker(last_block:Block):
            self.chain_switch_events.append(LocalChainTracker.ChainSwitchEvent(self.current_round,
                                                                                      last_block, miner_id))
        return tracker
    
    # def get_merge_tracker(self, miner_id:int):
    #     block_merge_round_per_miner = dict()
    #     self.block_merge_round[miner_id] = block_merge_round_per_miner
    #     def tracker(last_block:Block):
    #         block_merge_round_per_miner[last_block.blockhash] = self.current_round

    #     return tracker
    
    def update_round(self,current_round):
        self.current_round = current_round

    def dump_events(self, filename: str, chains: list[Chain] = None,
                    honest_miner_ids: list[int] = None):
        dump_data = {'chain_switch_events': self.chain_switch_events}
        if chains is not None:
            chain_state = []
            for chain in chains:
                chain_copy = copy.deepcopy(chain)
                chain_state.append(chain_copy)
            dump_data['chains'] = chain_state
        if honest_miner_ids is not None:
            dump_data['honest_miner_ids'] = honest_miner_ids
        '''将链切换事件记录到文件'''
        import pickle
        with open(filename, 'wb') as f:
            pickle.dump(dump_data, f)
