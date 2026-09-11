import copy
import logging
from array import array
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
        self.block_set = {}
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

    def search_block_by_hash(self, blockhash: bytes):
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

    def add_blocks(self, blocks: Block | list[Block], insert_point:Block=None,
                   deepcopy: bool = True):
        if not blocks:
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
            add_block_list.append(copy.deepcopy(blocks) if deepcopy else blocks)
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
            add_block_list.extend(copy.deepcopy(checklist) if deepcopy else checklist)

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
        if len(copylist) > 0 and local_tmp:
            # 返回深拷贝的最后一个区块的指针
            return self.add_blocks(blocks=copylist,insert_point=local_tmp)
        elif len(copylist) == 0 and local_tmp:
            # 如果没拷贝且block已经在链上，返回链上的block
            return local_tmp
        else:
            # 链头不一致
            return None

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
        return show_structure(self)

    def ShowStructure(self, miner_num=10):
        return plot_structure(self, miner_num)

    def ShowStructureWithGraphviz(self, other_list=None):
        return render_graphviz(self, other_list)

    def GetBlockIntervalDistribution(self):
        return plot_intervals(self)

    def printchain2txt(self, chain_data_url="chain_data.txt"):
        return printchain2txt(self, chain_data_url)

    def CalculateStatistics(
        self,
        rounds,
        honest_miners,
        adver_ids,
        confirm_delay,
        dataitem_params,
        valid_dataitems,
        quantile,
        eclipsed_ids=None,
        chain_switch_events=None,
    ):
        return calculate_statistics(
            self,
            rounds,
            honest_miners,
            adver_ids,
            confirm_delay,
            dataitem_params,
            valid_dataitems,
            quantile,
            eclipsed_ids,
        )

    def set_switch_tracker_callback(self, callback):
        self.switch_tracker_callback = callback

    def set_merge_tracker_callback(self, callback):
        self.merge_tracker_callback = callback

    def set_merge_callback(self, callback):
        self.merge_callback = callback


def printchain2txt(chain, chain_data_url):
    snapshot = chain.collect_visible_tree()
    chain_data_path = global_var.get_chain_data_path()
    with open(chain_data_path / chain_data_url, 'a') as output:
        if len(snapshot) == 0:
            print("empty chain", file=output)
            return
        print("Blockchain maintained BY Miner", chain.miner_id, file=output)
        names = snapshot.names
        child_offsets = snapshot.child_offsets
        child_indices = snapshot.child_indices
        level = [0]
        while level:
            print("|    ", end="", file=output)
            print("-|   " * (len(level) - 1), file=output)
            print("".join(f"{names[index]}   " for index in level), file=output)
            level = [child for index in level
                     for child in child_indices[child_offsets[index]:child_offsets[index + 1]]]
        for blockhash in snapshot.hashes:
            print(chain.block_set[blockhash], file=output)


def _snapshot_levels(snapshot):
    child_offsets = snapshot.child_offsets
    child_indices = snapshot.child_indices
    level = [0] if len(snapshot) else []
    while level:
        yield level
        level = [child for index in level
                 for child in child_indices[child_offsets[index]:child_offsets[index + 1]]]


def show_structure(chain):
    snapshot = chain.collect_visible_tree()
    names = snapshot.names
    for level in _snapshot_levels(snapshot):
        print("|    ", end="")
        print("-|   " * (len(level) - 1))
        print("".join(f"{names[index]}   " for index in level))


def plot_structure(chain, miner_num):
    snapshot = chain.collect_visible_tree()
    names = snapshot.names
    heights = snapshot.heights
    timestamps = snapshot.timestamps
    miners = snapshot.miners
    adversarial = snapshot.adversarial
    genesis = snapshot.genesis
    parents = snapshot.parent_indices
    plt.figure()
    plt.rcParams['font.size'] = 16
    plt.rcParams['font.family'] = 'Times New Roman'
    for index, name in enumerate(names):
        if genesis[index]:
            plt.scatter(0, 0, color='b', marker='o')
            continue
        parent = parents[index]
        rd2 = timestamps[index] + miners[index] / miner_num
        rd1 = timestamps[parent] + miners[parent] / miner_num
        color = 'r' if adversarial[index] else 'b'
        plt.scatter(rd2, heights[index], color=color, marker='o')
        plt.plot([rd1, rd2], [heights[parent], heights[index]], color=color)
    plt.xlabel('Round')
    plt.ylabel('Block Height')
    plt.grid(True)
    result_path = global_var.get_result_path()
    plt.savefig(result_path / 'blockchain visualisation.svg')
    if global_var.get_show_fig():
        plt.show()
    plt.close()


def render_graphviz(chain, other_list):
    snapshot = chain.collect_visible_tree()
    names = snapshot.names
    miners = snapshot.miners
    adversarial = snapshot.adversarial
    genesis = snapshot.genesis
    parents = snapshot.parent_indices
    dot = graphviz.Digraph('Blockchain Structure', engine='dot')
    for index, name in enumerate(names):
        if genesis[index]:
            dot.node(name, shape='rect', color='black', fontsize='20')
            continue
        if adversarial[index]:
            color = 'red'
        elif other_list is None:
            color = 'blue'
        else:
            color = 'orange' if miners[index] in other_list else 'blue'
        dot.node(name, shape='rect', color=color)
        dot.edge(names[parents[index]], name)
    dot.render(directory=global_var.get_result_path() / "blockchain_visualization",
               format='svg', view=global_var.get_show_fig())


def plot_intervals(chain):
    path = chain.collect_ancestor_path(chain.last_block)
    timestamps = path.timestamps
    stat = [timestamps[index] - timestamps[index + 1]
            for index in range(len(timestamps) - 1)]
    bins = 10 if path.heights[0] <= 1000 else 20
    plt.rcParams['font.size'] = 16
    plt.rcParams['font.family'] = 'Times New Roman'
    plt.hist(stat, bins=bins, histtype='bar', range=(0, max(stat)))
    plt.xlabel('Rounds')
    plt.ylabel('Times')
    result_path = global_var.get_result_path()
    plt.savefig(result_path / 'block_interval_distribution.svg')
    if global_var.get_show_fig():
        plt.show()
    plt.close()


def _restore_snapshot_chain(miner_id, blocks, tip_hash):
    from .blockchain_tree import ChainFactory

    chain = ChainFactory().create(miner_id)
    for block in blocks:
        if block.isGenesis:
            chain.add_blocks(block)
            continue
        parent = chain.search_block_by_hash(block.blockhead.prehash)
        chain.add_blocks(block, insert_point=parent)
    if tip_hash is not None:
        chain.set_last_block(chain.search_block_by_hash(tip_hash))
    return chain


def calculate_statistics(chain, rounds, honest_miners, adver_ids, confirm_delay,
                         dataitem_params, valid_dataitems, quantile, eclipsed_ids):
    eclipsed_ids = eclipsed_ids or []
    snapshot = chain.collect_visible_tree()
    hashes = snapshot.hashes
    heights = snapshot.heights
    miners = snapshot.miners
    child_offsets = snapshot.child_offsets
    child_indices = snapshot.child_indices
    index_by_hash = {blockhash: index for index, blockhash in enumerate(hashes)}
    generated_blocks = max(len(snapshot) - 1, 0)
    stats = {
        "num_of_generated_blocks": generated_blocks,
        "height_of_longest_chain": max(heights, default=0),
        "num_of_valid_blocks": 0,
        "num_of_stale_blocks": 0,
        "stale_rate": 0,
        "num_of_forks": 0,
        "num_of_heights_with_fork": 0,
        "fork_rate": 0,
        "average_block_time_main": 0,
        "block_throughput_main": 0,
        "throughput_main_MB": 0,
        "average_block_time_total": 0,
        "block_throughput_total": 0,
        "throughput_total_MB": 0,
        "double_spending_success_times": 0,
        "attack_fail": 0,
    }

    honest_miner_ids = {miner.miner_id for miner in honest_miners}
    miners_by_height = sorted(
        honest_miners, key=lambda miner: miner.get_local_chain().get_height(), reverse=True)
    quantile = quantile if quantile > 0 else 1 / len(honest_miners)
    consensus_miner_num = max(int(len(honest_miners) * quantile), 1)
    honest_cp = chain.last_block
    for miner in miners_by_height[:consensus_miner_num]:
        honest_cp = chain.common_prefix(honest_cp, miner.get_local_chain().get_last_block())
    stats["num_of_valid_blocks"] = honest_cp.height
    main_path = chain.collect_ancestor_path(honest_cp)

    valid_item_count = 0
    anomalous_item_count = 0
    if dataitem_params['dataitem_enable']:
        dataitem_set = set()
        dataitems_reversed = array('Q')
        for content in main_path.contents:
            dataitems_reversed.extend(reversed(array('Q', content)))
        previous_item = int.from_bytes((255).to_bytes(1, BYTE_ORDER) * 2 * INT_LEN, BYTE_ORDER)
        for dataitem in dataitems_reversed:
            if dataitem.to_bytes(2 * INT_LEN, BYTE_ORDER) in valid_dataitems:
                if previous_item < dataitem and dataitem_params['dataitem_input_interval'] > 0:
                    anomalous_item_count += 1
                    logger.warning("A dataitem is out of order: %s", dataitem)
                else:
                    valid_item_count += 1
                    previous_item = dataitem
                    if dataitem in dataitem_set:
                        logger.warning("A dataitem duplicates")
                    else:
                        dataitem_set.add(dataitem)
            else:
                anomalous_item_count += 1
        stats.update({
            'valid_dataitem_throughput': valid_item_count / rounds,
            'input_dataitem_rate': 1 / dataitem_params['dataitem_input_interval']
                if dataitem_params['dataitem_input_interval'] > 0 else valid_item_count / rounds,
        })
        item_count = valid_item_count + anomalous_item_count
        if stats['num_of_valid_blocks'] > 0:
            stats['block_average_size'] = (
                item_count * dataitem_params['dataitem_size'] / stats['num_of_valid_blocks'])
            stats['valid_dataitem_rate'] = valid_item_count / item_count if item_count else 0
        else:
            stats['valid_dataitem_rate'] = 0
            stats['block_average_size'] = 0

    main_hashes = set(main_path.hashes)
    attacker_ids = set(adver_ids) | set(eclipsed_ids)
    for parent_hash in main_path.hashes[1:]:
        parent_index = index_by_hash[parent_hash]
        children = child_indices[child_offsets[parent_index]:child_offsets[parent_index + 1]]
        stats["num_of_forks"] += len(children) - 1
        stats["num_of_heights_with_fork"] += len(children) > 1
        if len(children) <= 1:
            continue
        attacker_main = next((child for child in children
                              if miners[child] in attacker_ids and hashes[child] in main_hashes), None)
        if attacker_main is None:
            continue
        for orphan_root in children:
            if orphan_root == attacker_main or miners[orphan_root] not in honest_miner_ids:
                continue
            longest = 0
            stack = [(orphan_root, 1)]
            while stack:
                current, depth = stack.pop()
                longest = max(longest, depth)
                stack.extend((child, depth + 1) for child in
                             child_indices[child_offsets[current]:child_offsets[current + 1]])
            if longest >= confirm_delay:
                stats["double_spending_success_times"] += 1
                break

    adversary_block_num = sum(miner in adver_ids for miner in main_path.miners)
    honest_block_num = len(main_path) - adversary_block_num
    stats.update({
        'chain_quality_property': {
            'Honest Block': honest_block_num,
            'Adversary Block': adversary_block_num,
        },
        'ratio_of_blocks_contributed_by_malicious_players': round(
            adversary_block_num / len(main_path), 5),
        'upper_bound t/(n-t)': round(len(adver_ids) / len(honest_miner_ids), 5),
    })

    valid_blocks = stats["num_of_valid_blocks"]
    stats["num_of_stale_blocks"] = generated_blocks - valid_blocks
    stats["average_block_time_main"] = rounds / valid_blocks if valid_blocks > 0 else -1
    stats["block_throughput_main"] = valid_blocks / rounds
    blocksize = global_var.get_blocksize()
    stats["throughput_main_MB"] = blocksize * stats["block_throughput_main"]
    stats["average_block_time_total"] = rounds / generated_blocks if generated_blocks else -1
    stats["block_throughput_total"] = generated_blocks / rounds
    stats["throughput_total_MB"] = blocksize * stats["block_throughput_total"]
    stats["fork_rate"] = stats["num_of_heights_with_fork"] / valid_blocks if valid_blocks else 0
    stats["stale_rate"] = stats["num_of_stale_blocks"] / generated_blocks if generated_blocks else 0
    return stats


def double_spending_success_by_switch(honest_chains:list[Chain], adver_ids:list[int], mainchain_block:dict,
                            confirm_delay: int, eclipsed_ids:list[int], chain_switch_events:list,
                            quantile: float):
    from external import common_prefix
    miner_num = global_var.get_miner_num()
    local_chain_tip_name = ['B0'] * miner_num
    local_chain_tip_hash = [honest_chains[0].head] * miner_num
    honest_miner_ids = [chain.miner_id for chain in honest_chains]

    def search_in_global_view(blockhash):
        for chain in honest_chains:
            block = chain.search_block_by_hash(blockhash)
            if block is not None:
                return block
        return None

    chain_override_events = {} # {fork_block: {"block_height", "switching_subjects"}}
    for event in chain_switch_events:
        if event.subject not in honest_miner_ids:
            # 仅关注诚实矿工
            continue
        if local_chain_tip_name[event.subject] not in mainchain_block and event.name in mainchain_block:
            # 从分叉切换到主链
            switch_source_block = search_in_global_view(local_chain_tip_hash[event.subject])
            if switch_source_block is None:
                print(local_chain_tip_name[event.subject])
            switch_target_block = mainchain_block[event.name]
            fork_block = common_prefix(switch_source_block, switch_target_block)
            if switch_source_block.get_height() - fork_block.get_height() >= confirm_delay:
                # 达到N=2的标准
                flag = False
                blocktmp = switch_target_block
                while blocktmp.blockhash != fork_block.blockhash:
                    if blocktmp.blockhead.miner in adver_ids or blocktmp.blockhead.miner in eclipsed_ids:
                        # 主链上有一个攻击者或者被月蚀攻击矿工的块
                        flag = True
                        break
                    blocktmp = blocktmp.parentblock
                if flag:
                    # 认定为一次override事件
                    default_item = {'block_height': fork_block.get_height(), 'switching_subjects': {}}
                    chain_override_events.setdefault(fork_block.name, default_item)
                    chain_override_events[fork_block.name]['switching_subjects'].setdefault(event.subject,[])
                    chain_override_events[fork_block.name]['switching_subjects'][event.subject].append((event.switch_round,
                                                                                                        switch_source_block,
                                                                                                        switch_target_block))                    
        local_chain_tip_name[event.subject] = event.name
        local_chain_tip_hash[event.subject] = event.blockhash
    
    success_history_reanalysis = {} # {fork_block: {"block_height", "switching_subjects"}}
    for fork_block, switch_event in chain_override_events.items():
        switch_history = switch_event['switching_subjects']
        if len(switch_history) >= quantile * len(honest_miner_ids):
            # 认定为攻击成功
            success_history_reanalysis[fork_block] = switch_history

    return len(success_history_reanalysis)


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
