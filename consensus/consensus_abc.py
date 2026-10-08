import copy
import logging
import random
from abc import ABCMeta, abstractmethod

import data
import global_var
from functions import BYTE_ORDER, HASH_LEN

logger = logging.getLogger(__name__)

class Consensus(metaclass=ABCMeta):        #抽象类
    genesis_blockheadextra_prp = {}
    genesis_blockextra_prp = {}
    genesis_blockheadextra_vt = {}
    genesis_blockextra_vt = {}

    class BlockHead(data.BlockHead):
        '''表述BlockHead的抽象类，重写初始化方法但是calculate_blockhash未实现'''
        def __init__(self, preblock:data.Block=None, timestamp=0, content=0, miner_id=-1, parentMT_root=0, contentMT_root=0):
            '''此处的默认值为创世区块中的值'''
            prehash = preblock.blockhash if preblock else (0).to_bytes(HASH_LEN, BYTE_ORDER)
            super().__init__(prehash, timestamp, content, miner_id, parentMT_root, contentMT_root)

    class Block(data.Block):
        '''与chain.Block功能相同但是重写初始化方法'''
        def __init__(self, blockhead: data.BlockHead, preblock: data.Block = None,
                     isadversary=False, blocksize_MB=2, index = None, vtonprp: list = [], txpool: list = [], prppool: list = []):
            '''当preblock没有指定时默认为创世区块，高度为0'''
            block_number = global_var.get_block_number() if preblock else 0
            height = preblock.height+1 if preblock else 0
            is_genesis = False if preblock else True
            vtonprp = list(vtonprp)
            txpool = list(txpool)
            prppool = list(prppool)
            super().__init__(f"B{block_number}", blockhead, height, 
                             isadversary, is_genesis, blocksize_MB, index, vtonprp, txpool, prppool)
            if global_var.get_delayed_self_receive():
                self.parentblock = preblock

    def create_genesis_block(self, chain:data.Chain, blockheadextra:dict = None, 
                             blockextra:dict = None):
        '''为指定链生成创世区块'''
        genesis_blockhead = self.BlockHead()
        for k,v in blockheadextra or {}:
            setattr(genesis_blockhead,k,v)
        chain.add_blocks(blocks=self.Block(genesis_blockhead))
        for k,v in blockextra or {}:
            setattr(chain.head,k,v)

    def __init__(self,miner_id):
        self.miner_id = miner_id
        self.local_chain_prp = data.Chain(miner_id)   # 维护的区块链
        self.local_chain_vt = [data.Chain(miner_id) for _ in range(global_var.get_vtnum())]  # 维护的区块链
        self.create_genesis_block(self.local_chain_prp,self.genesis_blockheadextra_prp,self.genesis_blockextra_prp)
        for vtchain in self.local_chain_vt:
            self.create_genesis_block(vtchain, self.genesis_blockheadextra_vt,
                                      self.genesis_blockextra_vt)
        self._receive_tape_tx:list[data.Message] = [] # 接收到的消息
        self._receive_tape_prp: list[data.Message] = []  # 接收到的消息
        self._receive_tape_vt: list[data.Message] = []  # 接收到的消息
        self.votesOnPrpBks: list[list[data.Message]] = [[] for _ in range(global_var.get_vtnum())]
        self._block_buffer:dict[bytes, list[Consensus.Block]] = {} # 区块缓存
        self.unref_tx:  list = []
        self.unref_prp: list = []

    def remove_unreftx(self, item):
        if item in self.unref_tx:
            self.unref_tx.remove(item)


    def remove_unrefprp(self, item):
        if item in self.unref_prp:
            self.unref_prp.remove(item)

    def in_local_chain(self,block:data.Block):
        '''Check whether a block is in local chain,
        param: block: The block to be checked
        return: Whether the block is in local chain.'''
        if self.local_chain_prp.search_block(block) is None:
            # logger.info("M%d %s not in local chain", self.miner_id, block.name)
            return False
        for chain in self.local_chain_vt:
            if chain.search_block(block) is None:
                return False
        return True

    def in_local_chain_prp(self, block: data.Block):
        '''Check whether a block is in local chain,
        param: block: The block to be checked
        return: Whether the block is in local chain.'''
        if self.local_chain_prp.search_block(block) is None:
            # logger.info("M%d %s not in local chain", self.miner_id, block.name)
            return False
        return True

    def in_local_chain_vt(self, block: data.Block):
        '''Check whether a block is in any of the local chains in local_chain_vt.
        param: block: The block to be checked
        return: Whether the block is in any of the local chains in local_chain_vt.'''
        index = block.index
        if self.local_chain_vt[index-2].search_block(block) is None:
            return False
        return True

    def receive_block(self,rcvblock:Block):
        '''Interface between network and miner. 
        Append the rcvblock(have not received before) to receive_tape, 
        and add to local chain in the next round. 
        :param rcvblock: The block received from network. (Block)
        :return: If the rcvblock not in local chain or receive_tape, return True.
        '''
        segment_index = rcvblock.index
        # print(f'receive block{rcvblock.name} and index:{rcvblock.index}')
        if segment_index == 0:
            if rcvblock in self._receive_tape_tx:
                return False
            if block_list := self._block_buffer.get(rcvblock.blockhead.prehash, None):
                for block in block_list:
                    if block.blockhash == rcvblock.blockhash:
                        return False
            self._receive_tape_tx.append(rcvblock)
            self.unref_tx.append(rcvblock.name)
            # print(f"success receive block{rcvblock.name} mined by {rcvblock.blockhead.miner} The value of segment_index is: {segment_index}")
            random.shuffle(self._receive_tape_tx)
            return True
        elif segment_index == 1:
            if rcvblock in self._receive_tape_prp:
                return False
            if block_list := self._block_buffer.get(rcvblock.blockhead.prehash, None):
                for block in block_list:
                    if block.blockhash == rcvblock.blockhash:
                        return False
            if self.in_local_chain_prp(rcvblock):
                return False
            self._receive_tape_prp.append(rcvblock)
            self.unref_prp.append(rcvblock.name)
            print(f"miner {self.miner_id} success receive block{rcvblock.name} mined by {rcvblock.blockhead.miner} The value of segment_index is: {segment_index}")
            now_lastblock_prp = self.local_chain_prp.get_last_block()
            if rcvblock.height >= now_lastblock_prp.height + 1:
                print(f'miner {self.miner_id} received prp block{rcvblock.name} and height {rcvblock.height} and lastblock: {now_lastblock_prp.name}')
                for i, vt_chain in enumerate(self.local_chain_vt):
                    # 检查 vt_chain 是否已经对 prp_block.height 投过票
                    if not vt_chain.has_voted(rcvblock.height):
                        print(f'miner {self.miner_id} vote block{rcvblock.name} and height {rcvblock.height}')
                        # 如果没有投过票，那么在 vt_chain 上投票
                        vt_chain.vote(rcvblock.height, rcvblock)

                        # 并且将 rcvblock.name 添加到对应的 self.votesOnPrpBks 中的列表
                        self.votesOnPrpBks[i].append(rcvblock)
                # print(f"get vote{self.votesOnPrpBks[i]}")
            else:
                pass
                print(f"need ReqestNetwork function because rc{rcvblock.name} mined by {rcvblock.blockhead.miner} at height{rcvblock.height} and now_lastprp{now_lastblock_prp.name}mined by {now_lastblock_prp.blockhead.miner} height{now_lastblock_prp.height}")
            for block in rcvblock.txblock:
                self.remove_unreftx(block)
            for block in rcvblock.prpblock:
                self.remove_unrefprp(block)
            random.shuffle(self._receive_tape_prp)
        elif segment_index < (global_var.get_vtnum() + 2):
            if rcvblock in self._receive_tape_vt:
                return False
            if block_list := self._block_buffer.get(rcvblock.blockhead.prehash, None):
                for block in block_list:
                    if block.blockhash == rcvblock.blockhash:
                        return False
            if self.in_local_chain_vt(rcvblock):
                return False
            # print(
            #     f"success receive block{rcvblock.name} mined by {rcvblock.blockhead.miner} The value of segment_index is: {segment_index}")
            self._receive_tape_vt.append(rcvblock)
            now_lastblock_vt = self.local_chain_vt[segment_index - 2].get_last_block()
            now_height = now_lastblock_vt.height if now_lastblock_vt else 0
            if rcvblock.height > now_height:
                adver_ids = global_var.get_adver_ids()
                flag = global_var.get_attack_flag_ds()
                if self.miner_id not in adver_ids or (self.miner_id in adver_ids and not flag) or (self.miner_id in adver_ids and rcvblock.blockhead.miner in adver_ids):
                    before_votes = [b.name if hasattr(b, 'name') else str(b) for b in self.votesOnPrpBks[segment_index - 2]]
                    self.votesOnPrpBks[segment_index - 2] = [item for item in self.votesOnPrpBks[segment_index - 2] if
                                                             item not in rcvblock.vtonprp]
                    # print('remove before votes on')
                    # print(f'{self.votesOnPrpBks[segment_index - 2]}')
                    # print(f'worked by {self.miner_id}')
                    for prp_block in rcvblock.vtonprp:
                        if self.in_local_chain_prp(prp_block):
                            vtc = self.local_chain_vt[segment_index - 2]
                            if vtc.has_voted(prp_block.height):
                                old_block_name = vtc.votes[prp_block.height]
                                voteon = self.votesOnPrpBks[segment_index - 2]
                                if old_block_name in voteon:
                                    voteon.remove(old_block_name)
                                    vtc.votes[prp_block.height] = prp_block
                            else:
                                # 如果之前没有对该高度进行过投票，则直接记录新的投票
                                vtc.vote(prp_block.height, prp_block)
                        elif global_var.get_attack_execute_type() == 'DoubleSpending':
                            vtc = self.local_chain_vt[segment_index - 2]
                            if vtc.has_voted(prp_block.height):
                                old_block_name = vtc.votes[prp_block.height]
                                voteon = self.votesOnPrpBks[segment_index - 2]
                                if old_block_name in voteon:
                                    voteon.remove(old_block_name)
                                    vtc.votes[prp_block.height] = prp_block
                            else:
                                # 如果之前没有对该高度进行过投票，则直接记录新的投票
                                vtc.vote(prp_block.height, prp_block)

                    rcv_block_votes = [b.name if hasattr(b, 'name') else str(b) for b in rcvblock.vtonprp]
                    after_votes = [b.name if hasattr(b, 'name') else str(b) for b in self.votesOnPrpBks[segment_index - 2]]
                    if before_votes != after_votes:
                        log_file_path = 'D:/miner_vote_changes.txt'
                        with open(log_file_path, 'a', encoding='utf-8') as f:
                            f.write(f"Miner {self.miner_id} | VtChain {segment_index - 2} | RcvBlock {rcvblock.name} (Height: {rcvblock.height}, Miner: {rcvblock.blockhead.miner})\n")
                            f.write(f"  RcvBlock Votes: {rcv_block_votes}\n")
                            f.write(f"  Before        : {before_votes}\n")
                            f.write(f"  After         : {after_votes}\n\n")

                    # print('remove after votes on')
                    # print(f'{self.votesOnPrpBks[segment_index - 2]}')
            random.shuffle(self._receive_tape_vt)
        return True

    def synthesize_fork(self, conjunction_block:data.Block):
        '''根据新到的有效块与缓冲区中的空悬块合成完整分支'''
        touched_blocks:list[data.Block] = [conjunction_block]
        tip = conjunction_block
        for block in touched_blocks:
            # 提取block之后一高度的块
            if (trailing_blocks := self._block_buffer.get(block.blockhash, None)) is None:
                continue
            for fork_tip in trailing_blocks:
                if fork_tip.index == 1:
                    tip = self.local_chain_prp.add_blocks(blocks=[fork_tip], insert_point=block) # 放入本地链
                    touched_blocks.append(tip) # 以fork_tip的哈希为键查找下一高度块
                elif fork_tip.index <= (global_var.get_vtnum()+2):
                    tip = self.local_chain_vt[fork_tip.index-2].add_blocks(blocks=[fork_tip], insert_point=block)  # 放入本地链
                    touched_blocks.append(tip)  # 以fork_tip的哈希为键查找下一高度块
        for block in touched_blocks:
            if block.blockhash in self._block_buffer:
                del self._block_buffer[block.blockhash]

        return tip, touched_blocks

    def receive_filter(self, msg: data.Message):
        '''接收事件处理，调用相应函数处理传入的对象'''
        if isinstance(msg, data.Block):
            return self.receive_block(msg)
        

    def consensus_process(self, isadversary, x, round):
        '''典型共识过程：挖出新区块并添加到本地链
        return:
            msg_list 包含挖出的新区块的列表，无新区块则为None type:list[Block]/None
            msg_available 如果有新的消息产生则为True type:Bool
        '''
        newblock, success = self.mining_consensus(self.miner_id , isadversary, x, round, None, None)
        if success is False:
            return None, False
        if not global_var.get_delayed_self_receive():
            if newblock.index == 0:
                pass
            elif newblock.index == 1:
                newblock = self.local_chain_prp.add_blocks(blocks=newblock)
            else:
                newblock = self.local_chain_vt[newblock.index-2].add_blocks(blocks=newblock)
        # add_blocks默认执行深拷贝 因此要获取当前加到链上的newblock地址
        # self.local_chain.lastblock = newblock
        logger.info("round %d, M%d mined %s", round, self.miner_id, newblock.name)
        return [newblock], True # 返回挖出的区块
            

    @abstractmethod
    def setparam(self,**consensus_params):
        '''设置共识所需参数'''
        pass

    @abstractmethod
    def mining_consensus(self, miner_id, isadversary, x, round, miner, necessary_blocks):
        '''共识机制定义的挖矿算法
        return:
            新产生的区块  type:Block 
            挖矿成功标识    type:bool
        '''
        pass

    @abstractmethod
    def local_state_update(self):
        '''检验接收到的区块并将其合并到本地链'''
        pass

    @abstractmethod
    def valid_chain(self):
        '''检验链是否合法
        return:
            合法标识    type:bool
        '''
        pass

    @abstractmethod
    def valid_block(self):
        '''检验单个区块是否合法
        return:合法标识    type:bool
        '''
        pass
