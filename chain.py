import copy
from typing import List
from abc import ABCMeta, abstractmethod

import graphviz
import matplotlib.pyplot as plt

import global_var
from functions import hashG, hashH
from network import Message

class BlockHead(metaclass=ABCMeta):
    __omit_keys = {}
    def __init__(self, prehash=None, timestamp=None, content = None, Miner=None):
        self.prehash = prehash  # 前一个区块的hash
        self.timestamp = timestamp  # 时间戳
        self.content = content
        self.miner = Miner  # 矿工
    
    @abstractmethod
    def calculate_blockhash(self):
        '''
        计算区块的hash
        return:
            hash type:str
        '''
        return hashH([self.miner, hashG([self.prehash, self.content])])

    def __repr__(self) -> str:
        bhlist = []
        for k, v in self.__dict__.items():
            if k not in self.__omit_keys:
                bhlist.append(k + ': ' + str(v))
        return '\n'.join(bhlist)


class Block(Message):

    def __init__(self, name=None, blockhead: BlockHead = None, height = None, 
                 isadversary=False, isgenesis=False, blocksize_MB=2):
        self.name = name
        self._blockhead = blockhead
        self.height = height
        self.blockhash = blockhead.calculate_blockhash()
        self.isAdversaryBlock = isadversary
        self.next = []  # 子块列表
        self.last = None  # 母块
        self.isGenesis = isgenesis
        super().__init__(blocksize_MB)
        # super().__init__(int(random.uniform(0.5, 2)))
        # 单位:MB 随机 0.5~1 MB
        
    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if cls.__name__ == 'Block' and k != 'next' and k != 'last':
                setattr(result, k, copy.deepcopy(v, memo))
            if cls.__name__ == 'Block' and k == 'next':
                setattr(result, k, [])
            if cls.__name__ == 'Block' and k == 'last':
                setattr(result, k, None)
            if cls.__name__ != 'Block':
                setattr(result, k, copy.deepcopy(v, memo))
        return result

    __omit_keys = {}
    def __repr__(self) -> str:

        def _formatter(d, mplus=1):
            m = max(map(len, list(d.keys()))) + mplus
            s = '\n'.join([k.rjust(m) + ': ' + _indenter(str(v), m+2)
                            for k, v in d.items()])
            return s
        def _indenter(s, n=0):
            split = s.split("\n")
            indent = " "*n
            return ("\n" + indent).join(split)
        
        bdict = copy.deepcopy(self.__dict__)
        bdict.update({'next': [b.name for b in self.next if self.next], 
                      'last': self.last.name if self.last is not None else None})
        for omk in self.__omit_keys:
            del bdict[omk]
        return '\n'+ _formatter(bdict)

    @property
    def blockhead(self):
        return self._blockhead

    def calculate_blockhash(self):
        self.blockhash = self.blockhead.calculate_blockhash()
        return self.blockhash

    def BlockHeight(self):
        return self.height


class Chain(object):

    def __init__(self, miner_id = None):
        self.miner_id = miner_id
        self.head = None
        self.lastblock = self.head  # 指向最新区块，代表矿工认定的主链

    def __contains__(self, block: Block):
        if not self.head:
            return False
        q = [self.head]
        while q:
            blocktmp = q.pop(0)
            if block.blockhash == blocktmp.blockhash:
                return True
            for i in blocktmp.next:
                q.append(i)
        return False

    def __iter__(self):
        if not self.head:
            return
        q = [self.head]
        while q:
            blocktmp = q.pop(0)
            yield blocktmp
            for i in blocktmp.next:
                q.append(i)

    def __deepcopy__(self, memo):
        if not self.head:
            return None
        copy_chain = Chain()
        copy_chain.head = copy.deepcopy(self.head)
        memo[id(copy_chain.head)] = copy_chain.head
        q = [copy_chain.head]
        q_o = [self.head]
        copy_chain.lastblock = copy_chain.head
        while q_o:
            for block in q_o[0].next:
                copy_block = copy.deepcopy(block, memo)
                copy_block.last = q[0]
                q[0].next.append(copy_block)
                q.append(copy_block)
                q_o.append(block)
                memo[id(copy_block)] = copy_block
                if block.name == self.lastblock.name:
                    copy_chain.lastblock = copy_block
            q.pop(0)
            q_o.pop(0)
        return copy_chain

    def search(self, block: Block, searchdepth=500):
        # 利用区块哈希，搜索某块是否存在(搜索树)
        # 存在返回区块地址，不存在返回None
        if not self.head or not block:
            return None
        searchroot = self.lastblock
        if block.height < searchroot.height - searchdepth:
            return None  # 如果搜索的块高度太低 直接不搜了
        i = 0
        while searchroot and searchroot.last and i <= searchdepth:
            if block.blockhash == searchroot.blockhash:
                return searchroot
            else:
                searchroot = searchroot.last
                i = i + 1
        q = [searchroot]
        while q:
            blocktmp = q.pop(0)
            if block.blockhash == blocktmp.blockhash:
                return blocktmp
            for i in blocktmp.next:
                q.append(i)
        return None

    def search_chain(self, block: Block, searchdepth=500):
        # 利用区块哈希，搜索某块是否在链上
        # 存在返回区块地址，不存在返回None
        if not self.head:
            return None
        blocktmp = self.lastblock
        i = 0
        while blocktmp and i <= searchdepth:
            if block.blockhash == blocktmp.blockhash:
                return blocktmp
            blocktmp = blocktmp.last
            i = i + 1
        return None

    def last_block(self):  # 返回最深的block，空链返回None
        return self.lastblock

    def is_empty(self):
        if not self.head:
            print("Chain Is empty")
            return True
        else:
            return False

    def Popblock(self):
        popb = self.last_block()
        last = popb.last
        if not last:
            return None
        else:
            last.next.remove(popb)
            popb.last = None
            return popb

    def add_block_direct(self, block: Block):
        # 将block直接添加到主链末尾，并将lastblock指向block
        # 和add_block_copy的区别是这个是不拷贝直接连接的
        if self.search(block):
            print("Block {} is already included.".format(block.name))
            return block

        if not self.head:
            self.head = block
            self.lastblock = block
            # print("Add Block {} Successfully.".format(block.name))
            return block

        last_Block = self.last_block()
        last_Block.next.append(block)
        block.last = last_Block
        self.lastblock = block
        # print("Add Block {} Successfully.".format(block.name))
        return block


    def insert_block_copy(self, copylist: List[Block], insert_point: Block):
        '''在指定的插入点将指定的链合入区块树
        param:
            copylist 待插入的链 type:List[Block]
            insert_point 区块树中的节点，copylist中的链从这里插入 type:Block
        return:
            local_tmp 返回值：深拷贝插入完之后新插入链的块头 type:Block
        '''
        local_tmp = insert_point
        if local_tmp:
            while copylist:
                receive_tmp = copylist.pop()
                blocktmp = copy.deepcopy(receive_tmp)
                blocktmp.last = local_tmp
                blocktmp.next = []
                local_tmp.next.append(blocktmp)
                local_tmp = blocktmp
        return local_tmp  # 返回深拷贝的最后一个区块的指针，如果没拷贝返回None

    def add_block_copy(self, lastblock: Block):
        # 返回值：深拷贝插入完之后新插入链的块头
        receive_tmp = lastblock
        if not receive_tmp:  # 接受的链为空，直接返回
            return None
        copylist = []  # 需要拷贝过去的区块list
        local_tmp = self.search(receive_tmp)
        while receive_tmp and not local_tmp:
            copylist.append(receive_tmp)
            receive_tmp = receive_tmp.last
            local_tmp = self.search(receive_tmp)
        if local_tmp:
            while copylist:
                receive_tmp = copylist.pop()
                blocktmp = copy.deepcopy(receive_tmp)
                blocktmp.last = local_tmp
                blocktmp.next = []
                local_tmp.next.append(blocktmp)
                local_tmp = blocktmp
            if local_tmp.BlockHeight() > self.lastblock.BlockHeight():
                self.lastblock = local_tmp  # 更新global chain的lastblock
        return local_tmp  # 返回深拷贝的最后一个区块的指针，如果没拷贝返回None

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
        cur = self.last_block()
        blocklist = []
        while cur:
            # print(cur.name)
            blocklist.append(cur)
            cur = cur.last
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
        blocktmp = self.head
        fork_list = []
        while blocktmp:
            if blocktmp.isGenesis is False:
                rd2 = blocktmp.blockhead.content + blocktmp.blockhead.miner / miner_num
                rd1 = blocktmp.last.blockhead.content + blocktmp.last.blockhead.miner / miner_num
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
        plt.xlabel('round')
        plt.ylabel('block height')
        plt.title('blockchain visualisation')
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
                dot.edge(blocktmp.last.name, blocktmp.name)
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

    def get_block_interval_distribution(self):
        stat = []
        blocktmp2 = self.lastblock
        while not blocktmp2.isGenesis:
            blocktmp1 = blocktmp2.last
            stat.append(blocktmp2.blockhead.content - blocktmp1.blockhead.content)
            blocktmp2 = blocktmp1
        plt.hist(stat, bins=10, histtype='bar', range=(0, max(stat)))
        plt.xlabel('Rounds')
        plt.ylabel('Times')
        plt.title('Block generation interval distribution')
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

        last_block = self.lastblock.last
        while last_block:
            stats["num_of_forks"] += len(last_block.next) - 1
            last_block = last_block.last

        stats["num_of_stale_blocks"] = stats["num_of_generated_blocks"] - stats["num_of_valid_blocks"]
        stats["average_block_time_main"] = rounds / stats["num_of_valid_blocks"]
        stats["block_throughput_main"] = stats["num_of_valid_blocks"] / rounds
        blocksize = global_var.get_blocksize()
        stats["throughput_main_MB"] = blocksize * stats["block_throughput_main"]
        stats["average_block_time_total"] = rounds / stats["num_of_generated_blocks"]
        stats["block_throughput_total"] = 1 / stats["average_block_time_total"]
        stats["throughput_total_MB"] = blocksize * stats["block_throughput_total"]
        stats["fork_rate"] = stats["num_of_forks"] / stats["num_of_valid_blocks"]
        stats["stale_rate"] = stats["num_of_stale_blocks"] / stats["num_of_generated_blocks"]

        return stats

