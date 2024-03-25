import copy

import graphviz
import matplotlib.pyplot as plt

import global_var
from collections import defaultdict

from .block import Block


class Chain(object):

    def __init__(self, miner_id = None):
        self.miner_id = miner_id
        self.head = None
        self.last_block = self.head  # 指向最新区块，代表矿工认定的主链
        self.block_set = defaultdict(Block)
        '''
        默认的共识机制中会对chain添加一个创世区块
        默认情况下chain不可能为空
        '''

    def __deepcopy__(self, memo):
        if self.head is None:
            return None
        copy_chain = Chain()
        copy_chain.head = copy.deepcopy(self.head)
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
        else:
            return

    def get_height(self,block:Block=None):
        # 默认返回最深区块的高度
        # 或者返回指定区块的高度
        if block is not None:
            return block.get_height()
        else:
            return self.get_last_block().get_height()

    def add_blocks(self, blocks, insert_point:Block=None):
        # 添加区块的功能 (深拷贝*)
        # item是待添加的内容 可以是list[Block]类型 也可以是Block类型
        # 即可以批量添加也可以只添加一个区块
        # inset_point 是插入区块的位置 从其后开始添加 默认为最深链
        '''
        添加区块的功能不会考虑区块前后的hash是否一致
        这个任务不属于数据层 是共识层的任务
        数据层只负责添加
        '''
        add_block_list:list[Block]=[]
        if isinstance(blocks,Block):
            add_block_list.append(copy.deepcopy(blocks))
        else:
            add_block_list.extend(copy.deepcopy(blocks))
        if insert_point is None:
            insert_point = self.get_last_block()

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

        # 如果新加的区块的高度比现在的链的高度高 重新将lastblock指向新加区块
        if cur2add.get_height() > self.get_height():
            self.set_last_block(cur2add)
        return cur2add

    def _add_block_forcibly(self, block: Block):
        # 该功能是强制将该区块加入某条链 一般不被使用与共识中
        # 只会被globalchain调用 
        # 返回值：深拷贝插入完之后新插入链的块头
        # block 的 last必须不为none
        # 不会为block默认赋值 要求使用该方法必须给出添加的区块 否则提示报错

        copylist:list[Block] = []  # 需要拷贝过去的区块list
        local_tmp = self.search_block(block)
        while block and not local_tmp:
            copylist.append(block)
            block = block.parentblock
            local_tmp = self.search_block(block)

        if local_tmp:
            self.add_blocks(blocks=copylist,insert_point=local_tmp)
        return local_tmp  # 返回深拷贝的最后一个区块的指针，如果没拷贝返回None

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
                rd2 = blocktmp.blockhead.content + blocktmp.blockhead.miner / miner_num
                rd1 = blocktmp.parentblock.blockhead.content + blocktmp.parentblock.blockhead.miner / miner_num
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

    def ShowStructureWithGraphviz(self):
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
                    dot.node(blocktmp.name,shape='rect',color='blue')
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
            stat.append(blocktmp2.blockhead.content - blocktmp1.blockhead.content)
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
        plt.savefig(RESULT_PATH / 'block interval distribution.svg')
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


    def CalculateStatistics(self, rounds):
        # 统计一些数据
        stats = {
            "num_of_generated_blocks": -1,
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
            "throughput_total_MB": 0
        }
        q = [self.head]
        while q:
            stats["num_of_generated_blocks"] = stats["num_of_generated_blocks"] + 1
            blocktmp = q.pop(0)
            if blocktmp.height > stats["num_of_valid_blocks"]:
                stats["num_of_valid_blocks"] = blocktmp.height
            nextlist = blocktmp.next
            q.extend(nextlist)

        last_block = self.last_block.parentblock
        while last_block:
            stats["num_of_forks"] += len(last_block.next) - 1
            stats["num_of_heights_with_fork"] += (len(last_block.next) > 1)
            last_block = last_block.parentblock

        stats["num_of_stale_blocks"] = stats["num_of_generated_blocks"] - stats["num_of_valid_blocks"]
        stats["average_block_time_main"] = rounds / stats["num_of_valid_blocks"]
        stats["block_throughput_main"] = stats["num_of_valid_blocks"] / rounds
        blocksize = global_var.get_blocksize()
        stats["throughput_main_MB"] = blocksize * stats["block_throughput_main"]
        stats["average_block_time_total"] = rounds / stats["num_of_generated_blocks"]
        stats["block_throughput_total"] = 1 / stats["average_block_time_total"]
        stats["throughput_total_MB"] = blocksize * stats["block_throughput_total"]
        stats["fork_rate"] = stats["num_of_heights_with_fork"] / stats["num_of_valid_blocks"]
        stats["stale_rate"] = stats["num_of_stale_blocks"] / stats["num_of_generated_blocks"]

        return stats

