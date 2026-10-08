import random
import time
from typing import List, Tuple

import data
import global_var
from functions import BYTE_ORDER, INT_LEN, HASH_LEN, hash_bytes, merkle_root

from .consensus_abc import Consensus


class PoW(Consensus):

    class BlockHead(Consensus.BlockHead):
        '''适用于PoW共识协议的区块头'''
        def __init__(self, preblock: Consensus.Block = None, timestamp=0, content=0, miner_id=-1,
                     target = (2**(8*HASH_LEN) - 1).to_bytes(HASH_LEN, BYTE_ORDER),
                     nonce = 0, parentMT_root='', contentMT_root=''):
            # currently content is an integer equal to the round the block is generated
            super().__init__(preblock, timestamp, content, miner_id, parentMT_root, contentMT_root)
            self.target = target  # 难度目标
            self.nonce = nonce  # 随机数

        def calculate_blockhash(self) -> bytes:
            intermediate_hasher = hash_bytes(
                self.miner.to_bytes(INT_LEN, BYTE_ORDER, signed=True) +
                self.content.to_bytes(INT_LEN, BYTE_ORDER)+self.parentMT_root.encode() +
                    self.contentMT_root.encode())
            hasher = intermediate_hasher.copy()
            hasher.update(self.nonce.to_bytes(INT_LEN, BYTE_ORDER))
            currenthash = hasher.digest()
            return currenthash

    def __init__(self,miner_id,consensus_params:dict):
        super().__init__(miner_id=miner_id)
        self.ctr=0 #计数器
        self.target = bytes.fromhex(consensus_params['target'])
        if consensus_params['q_distr'] == 'equal':
            self.q = consensus_params['q_ave']
        else:
            q_distr = eval(consensus_params['q_distr'])
            if isinstance(q_distr,list):
                self.q = q_distr[miner_id]
            else:
                raise ValueError("q_distr should be a list or the string 'equal'")

    def setparam(self,**consensus_params):
        '''
        设置pow参数,主要是target
        '''
        self.target = bytes.fromhex(consensus_params.get('target') or self.target)
        self.q = consensus_params.get('q') or self.q

    def mining_consensus(self, miner_id:int, isadversary, x, round, miner, necessary_blocks):
        '''计算PoW\n
        param:
            Miner_ID 该矿工的ID type:int
            x 写入区块的内容 type:any
            qmax 最大hash计算次数 type:int
        return:
            newblock 挖出的新块 type:None(未挖出)/Block
            pow_success POW成功标识 type:Bool
        '''
        # start_time = time.time()
        pow_success = False

        prpContent = []
        txContent = []
        vtprehashes = [0] * global_var.get_vtnum()
        b_last_vt = [None for _ in range(global_var.get_vtnum())]
        target_int = int.from_bytes(self.target, 'big')
        segment_range = target_int // (global_var.get_vtnum() + 2)
        if self.miner_id == -1 and global_var.get_attack_execute_type() == 'DoubleSpending' and global_var.get_attack_flag_ds():
            vtContent = miner.consensus.votesOnPrpBks
            # 遍历每条链的投票内容
            # print(f'miner {miner.miner_id} votecontent before:')
            # for vtcon in vtContent:
            #     print(vtcon)
            if necessary_blocks != []:
                for i in range(len(vtContent)):
                    for vote in vtContent[i]:
                        for necessary_block in necessary_blocks:
                            if vote.height == necessary_block.height and vote.name != necessary_block.name:
                                print(f'has replaced {vote.name} on height {vote.height}')
                                # 替换投票内容
                                miner.consensus.votesOnPrpBks[i].remove(vote)
                                miner.consensus.votesOnPrpBks[i].append(necessary_block)
                                miner.consensus.local_chain_vt[i].votes[vote.height] = necessary_block
                                print(f'by {necessary_block} on height {necessary_block.height}')
                                break
            # print(f'miner {miner.miner_id} votecontent after:')
            # for vtcon in vtContent:
            #     print(vtcon)
        elif self.miner_id == -1 and global_var.get_attack_execute_type() == 'BalanceAttack' and global_var.get_attack_flag_BA():
            vtContent = miner.consensus.votesOnPrpBks
            # 遍历每条链的投票内容
            # for vt_chain_num in range(len(vtContent)):
            #     print(f'vtchain{vt_chain_num} has vote on {miner.consensus.local_chain_vt[vt_chain_num].votes}')
            # print(f'miner {miner.miner_id} has votecontent before:')
            if necessary_blocks != []:
                for vt_chain_num in range(len(vtContent)):
                    # for vote in vtContent[vt_chain_num]:
                    #     for necessary_block in necessary_blocks:
                    #         if vote.height == necessary_block.height and vote.name != necessary_block.name:
                    #             print(f'has replaced {vote.name} on height {vote.height}')
                    #             # 替换投票内容
                    #             miner.consensus.votesOnPrpBks[vt_chain_num].remove(vote)
                    #             miner.consensus.votesOnPrpBks[vt_chain_num].append(necessary_block)
                    #             miner.consensus.local_chain_vt[vt_chain_num].votes[vote.height] = necessary_block
                    #             print(f'by {necessary_block} on height {necessary_block.height}')
                    #             break
                    # 这部分处理一下平衡攻击中投票者块出块的位置
                    for minority_block in necessary_blocks:
                        # 已经投给落后块
                        if minority_block in miner.consensus.local_chain_vt[vt_chain_num].votes.values():
                            b_last_vt[vt_chain_num] = miner.consensus.local_chain_vt[vt_chain_num].get_last_block()
                            vtprehashes[vt_chain_num] = b_last_vt[vt_chain_num].blockhash
                            print('has in correct')
                        # 没有投给落后块
                        else:
                            ba_attack_height_vt = global_var.get_height_BA_vt()
                            heights = ba_attack_height_vt.get(minority_block.height, -1)
                            if heights == -1:
                                print('sth wrong in ba get height')
                            else:
                                print(f'will change to height {heights[vt_chain_num]}')
                                # 开始找应该跟在哪个投票者块后面
                                current_last_block = miner.consensus.local_chain_vt[vt_chain_num].get_last_block()
                                current_height = current_last_block.height
                                target_height = heights[vt_chain_num]

                                if current_height == target_height:
                                    # 如果当前链的最后一个块高度小于或等于目标高度
                                    b_last_vt[vt_chain_num] = current_last_block
                                    vtprehashes[vt_chain_num] = b_last_vt[vt_chain_num].blockhash
                                else:
                                    print('当前链的高度大于目标高度')
                                    # 当前链的高度大于目标高度
                                    # 查找高度为 target_height + 1 的块
                                    candidate_blocks = [
                                        block for block in miner.consensus.local_chain_vt[vt_chain_num]
                                        if block.get_height() == target_height + 1
                                    ]
                                    selected_block = None

                                    for block in candidate_blocks:
                                        # 检查是否包含 minority_block
                                        if minority_block in block.vtonprp:
                                            selected_block = block
                                            break

                                    if selected_block:
                                        # 找到合适的块，选择该块的最后一个子块########################################
                                        b_last_vt[vt_chain_num] = miner.consensus.local_chain_vt[
                                            vt_chain_num].find_last_child_block(selected_block)
                                        vtprehashes[vt_chain_num] = b_last_vt[vt_chain_num].blockhash
                                        print(f'has get ba last {b_last_vt[vt_chain_num]}')
                                    else:
                                        # 如果未找到满足条件的块，记录高度为 target_height 的块
                                        fallback_blocks = [
                                            block for block in miner.consensus.local_chain_vt[vt_chain_num]
                                            if block.get_height() == target_height
                                        ]
                                        print(f'fallback_blocks:{fallback_blocks}')
                                        if fallback_blocks:
                                            # 在这些块中随机选择一个
                                            b_last_vt[vt_chain_num] = random.choice(fallback_blocks)
                                            vtprehashes[vt_chain_num] = b_last_vt[vt_chain_num].blockhash
                                            global_prpchain = global_var.get_global_prpchain()
                                            votesblock = [minority_block]

                                            # 用于记录已添加的 block.height，避免重复添加相同高度的块
                                            added_heights = set()

                                            # 遍历 global_prpchain 中的所有块
                                            for block in global_prpchain:
                                                if block.height > minority_block.height and block.height not in added_heights:
                                                    # 添加当前块到 votesblock，并记录其高度
                                                    votesblock.append(block)
                                                    added_heights.add(block.height)
                                            vtContent[vt_chain_num] = votesblock
                                        else:
                                            print(
                                                f"Error: No blocks found at target height {target_height} for voter tree {vt_chain_num}.")
                    for vote in vtContent[vt_chain_num]:
                        for necessary_block in necessary_blocks:
                            if vote.height == necessary_block.height and vote.name != necessary_block.name:
                                print(f'has replaced {vote.name} on height {vote.height}')
                                # 替换投票内容
                                miner.consensus.votesOnPrpBks[vt_chain_num].remove(vote)
                                miner.consensus.votesOnPrpBks[vt_chain_num].append(necessary_block)
                                miner.consensus.local_chain_vt[vt_chain_num].votes[vote.height] = necessary_block
                                print(f'by {necessary_block} on height {necessary_block.height}')
                                break
            # print(f'miner {miner.miner_id} votecontent after:')
            # for vtcon in vtContent:
            #     print(vtcon)
        elif self.miner_id == -1 and global_var.get_attack_execute_type() == 'BalanceAttack' and not global_var.get_attack_flag_BA():
            vtContent = miner.consensus.votesOnPrpBks
        else:
            vtContent = self.votesOnPrpBks


        #print("mine",Blockchain)
        b_last_prp = self.local_chain_prp.get_last_block()#链中最后一个块
        prpprehash = b_last_prp.blockhash
        txprehash = prpprehash

        # # 这部分处理一下平衡攻击中投票者块出块的位置
        if isadversary and global_var.get_attack_execute_type() == 'BalanceAttack' and necessary_blocks != []:
            pass
        #     for vt_chain_num in range(len(vtContent)):
        #         print(f'now process vtContent{vt_chain_num}')
        #         for minority_block in necessary_blocks:
        #             # 已经投给落后块
        #             if minority_block in miner.consensus.local_chain_vt[vt_chain_num].votes.values():
        #                 b_last_vt[vt_chain_num] = miner.consensus.local_chain_vt[vt_chain_num].get_last_block()
        #                 vtprehashes[vt_chain_num] = b_last_vt[vt_chain_num].blockhash
        #                 print('has in correct')
        #             # 没有投给落后块
        #             else:
        #                 ba_attack_height_vt = global_var.get_height_BA_vt()
        #                 heights = ba_attack_height_vt.get(minority_block.height, -1)
        #                 if heights == -1:
        #                     print('sth wrong in ba get height')
        #                 else:
        #                     print(f'will change to height {heights[vt_chain_num]}')
        #                     # 开始找应该跟在哪个投票者块后面
        #                     current_last_block = miner.consensus.local_chain_vt[vt_chain_num].get_last_block()
        #                     current_height = current_last_block.height
        #                     target_height = heights[vt_chain_num]
        #
        #                     if current_height == target_height:
        #                         # 如果当前链的最后一个块高度小于或等于目标高度
        #                         b_last_vt[vt_chain_num] = current_last_block
        #                         vtprehashes[vt_chain_num] = b_last_vt[vt_chain_num].blockhash
        #                     else:
        #                         print('当前链的高度大于目标高度')
        #                         # 当前链的高度大于目标高度
        #                         # 查找高度为 target_height + 1 的块
        #                         candidate_blocks = [
        #                             block for block in miner.consensus.local_chain_vt[vt_chain_num]
        #                             if block.get_height() == target_height + 1
        #                         ]
        #                         selected_block = None
        #
        #                         for block in candidate_blocks:
        #                             # 检查是否包含 minority_block
        #                             if minority_block in block.vtonprp:
        #                                 selected_block = block
        #                                 break
        #
        #                         if selected_block:
        #                             # 找到合适的块，选择该块的最后一个子块########################################
        #                             b_last_vt[vt_chain_num] = miner.consensus.local_chain_vt[vt_chain_num].find_last_child_block(selected_block)
        #                             vtprehashes[vt_chain_num] = b_last_vt[vt_chain_num].blockhash
        #                             print(f'has get ba last {b_last_vt[vt_chain_num]}')
        #                         else:
        #                             # 如果未找到满足条件的块，记录高度为 target_height 的块
        #                             fallback_blocks = [
        #                                 block for block in miner.consensus.local_chain_vt[vt_chain_num]
        #                                 if block.get_height() == target_height
        #                             ]
        #                             print(f'fallback_blocks:{fallback_blocks}')
        #                             if fallback_blocks:
        #                                 # 在这些块中随机选择一个
        #                                 b_last_vt[vt_chain_num] = random.choice(fallback_blocks)
        #                                 vtprehashes[vt_chain_num] = b_last_vt[vt_chain_num].blockhash
        #                                 global_prpchain = global_var.get_global_prpchain()
        #                                 votesblock = [minority_block]
        #
        #                                 # 用于记录已添加的 block.height，避免重复添加相同高度的块
        #                                 added_heights = set()
        #
        #                                 # 遍历 global_prpchain 中的所有块
        #                                 for block in global_prpchain:
        #                                     if block.height > minority_block.height and block.height not in added_heights:
        #                                         # 添加当前块到 votesblock，并记录其高度
        #                                         votesblock.append(block)
        #                                         added_heights.add(block.height)
        #                                 vtContent[vt_chain_num] = votesblock
        #                             else:
        #                                 print(
        #                                     f"Error: No blocks found at target height {target_height} for voter tree {vt_chain_num}.")

        else:
            for vt_index, vt_chain in enumerate(self.local_chain_vt):
                b_last_vt[vt_index] = vt_chain.get_last_block()
                vtprehashes[vt_index] = b_last_vt[vt_index].blockhash

        if miner_id == -1:
            for r_tape_tx in miner.consensus.unref_tx:
                txContent.append(r_tape_tx)
            for r_tape_prp in miner.consensus.unref_prp:
                prpContent.append(r_tape_prp)

        else:
            for r_tape_tx in self.unref_tx:
                txContent.append(r_tape_tx)
            for r_tape_prp in self.unref_prp:
                prpContent.append(r_tape_prp)

        parentMT = [txprehash, prpprehash] + vtprehashes
        parentMT_root = merkle_root(parentMT)
        contentMT = [txContent] + [prpContent] + [vtContent]
        contentMT_root = merkle_root(contentMT)

        intermediate_hasher = hash_bytes(
            miner_id.to_bytes(INT_LEN, BYTE_ORDER, signed=True) +
            x.to_bytes(INT_LEN, BYTE_ORDER) + parentMT_root.encode() +
                    contentMT_root.encode())

        lastprp = self.local_chain_prp.get_last_block()

        i = 0
        while i < self.q:
            self.ctr += 1
            hasher = intermediate_hasher.copy()
            hasher.update(self.ctr.to_bytes(INT_LEN, BYTE_ORDER))
            currenthash = hasher.digest()  # 计算哈希

            currenthash_int = int.from_bytes(currenthash, 'big')


            if currenthash_int < target_int:
                global_var.add_block_generated()
                pow_success = True
                segment_index = currenthash_int // segment_range
                # print(f'get{segment_index}')

                if segment_index == 0:
                    blockhead = PoW.BlockHead(None, round, x, miner_id, self.target, self.ctr, parentMT_root,
                                              contentMT_root)
                    blocknew = PoW.Block(blockhead, None, isadversary, global_var.get_blocksize(), segment_index)
                    global_var.rec_tx()
                    tx = global_var.get_txnum()
                    blocknew.name = f'TX{tx}'
                    self.unref_tx.append(blocknew.name)
                elif segment_index == 1:
                    # 现在直接让双花攻击的时候不要出这个块
                    if not global_var.get_attack_flag_ds() or not isadversary:
                        self.unref_tx = []
                        self.unref_prp = []
                        blockhead = PoW.BlockHead(b_last_prp, round, x, miner_id, self.target, self.ctr, parentMT_root,
                                                  contentMT_root)
                        blocknew = PoW.Block(blockhead, b_last_prp, isadversary,  global_var.get_blocksize(), segment_index,
                                             [], txContent, prpContent)
                        # if not isadversary:
                        #     for i, vt_chain in enumerate(self.local_chain_vt):
                        #         if not vt_chain.has_voted(blocknew.height):
                        #             vt_chain.vote(blocknew.height, blocknew)
                        #             self.votesOnPrpBks[i].append(blocknew)
                        print(f'get block {blocknew.name} mined by {blocknew.blockhead.miner} index:{segment_index}')
                    else:
                        self.ctr = 0
                        return (None, False)
                elif segment_index < (global_var.get_vtnum() + 2):
                    blockhead = PoW.BlockHead(b_last_vt[segment_index - 2], round, x, miner_id, self.target, self.ctr,
                                              parentMT_root, contentMT_root)
                    blocknew = PoW.Block(blockhead, b_last_vt[segment_index - 2], isadversary,
                                         global_var.get_blocksize(), segment_index, list(vtContent[segment_index - 2]))
                    print(f'this powblock{blocknew.name} is produced by{self.miner_id} and height {blocknew.height} and lastblock: {b_last_vt[segment_index - 2]}')
                    # self.votesOnPrpBks[segment_index - 2] = []
                    # vtContent[segment_index - 2] = []
                else:
                    print(f"Invalid vt_chain_index. Index out of range.")

                self.ctr = 0
                # finish_time = time.time()
                # print(f'pow yongshi {finish_time-start_time}')
                return (blocknew, pow_success)
            else:
                i += 1
                lastprp.txblock = []
                # for vt_index, vt_chain in enumerate(self.vtBlockchain):
                #     if vt_chain.is_empty():  # 如果当前链为空
                #         vtprehashes[vt_index] = 0
                #     else:
                #         last_vt_block_fin = vt_chain.last_block()
                #         last_vt_block_fin.vtonprp = []
        # finish_time = time.time()
        # print(f'pow yongshi {finish_time - start_time}')
        return (None, pow_success)
        
        
    def local_state_update(self):
        # algorithm 2 比较自己的chain和收到的chain并相应更新本地链
        # output:
        #   lastblock 最长链的最新一个区块
        new_update = False  # 有没有更新
        #touched_hash_list = []
        for incoming_block in self._receive_tape_prp:
            if not isinstance(incoming_block, Consensus.Block):
                continue
            # print(f'verify success, get block{incoming_block.name} on index{incoming_block.index} by miner {self.miner_id}')
            if self.valid_block(incoming_block):
                prehash = incoming_block.blockhead.prehash
                if insert_point := self.local_chain_prp.search_block_by_hash(prehash):
                    conj_block = self.local_chain_prp.add_blocks(blocks=[incoming_block], insert_point=insert_point)
                    fork_tip, _ = self.synthesize_fork(conj_block)
                    #for block in touched_block:
                    #    touched_hash_list.append(block.blockhash)
                    depthself = self.local_chain_prp.get_height()
                    depth_incoming_block = fork_tip.get_height()
                    if depthself < depth_incoming_block:
                        self.local_chain_prp.set_last_block(fork_tip)
                        new_update = True
                else:
                    self._block_buffer.setdefault(prehash, [])
                    self._block_buffer[prehash].append(incoming_block)
        for incoming_block in self._receive_tape_vt:
            if not isinstance(incoming_block, Consensus.Block):
                continue
            # print(f'verify success, get block{incoming_block.name} on index{incoming_block.index}')
            if self.valid_block(incoming_block):
                prehash = incoming_block.blockhead.prehash
                if insert_point := self.local_chain_vt[incoming_block.index-2].search_block_by_hash(prehash):
                    conj_block = self.local_chain_vt[incoming_block.index-2].add_blocks(blocks=[incoming_block], insert_point=insert_point)
                    fork_tip, _ = self.synthesize_fork(conj_block)
                    #for block in touched_block:
                    #    touched_hash_list.append(block.blockhash)
                    depthself = self.local_chain_vt[incoming_block.index-2].get_height()
                    depth_incoming_block = fork_tip.get_height()
                    if depthself < depth_incoming_block:
                        self.local_chain_vt[incoming_block.index-2].set_last_block(fork_tip)
                        new_update = True
                else:
                    self._block_buffer.setdefault(prehash, [])
                    self._block_buffer[prehash].append(incoming_block)
        
        #self._block_buffer = {k: v for k, v in self._block_buffer.items() if k not in touched_hash_list}

        return self.local_chain_prp, new_update, self.local_chain_vt

    def valid_chain(self, lastblock: Consensus.Block):
        '''验证区块链是否PoW合法\n
        param:
            lastblock 要验证的区块链的最后一个区块 type:Block
        return:
            chain_vali 合法标识 type:bool
        '''
        # xc = external.R(blockchain)
        # chain_vali = external.V(xc)
        chain_vali = True
        if chain_vali and lastblock:
            blocktmp = lastblock
            ss = blocktmp.calculate_blockhash()
            while chain_vali and blocktmp is not None:
                hash=blocktmp.calculate_blockhash()
                block_vali = self.valid_block(blocktmp)
                if block_vali and hash == ss:
                    ss = blocktmp.blockhead.prehash
                    blocktmp = blocktmp.parentblock
                else:
                    chain_vali = False
        return chain_vali

    def valid_block(self,block:Consensus.Block):
        '''
        验证单个区块是否PoW合法\n
        param:
            block 要验证的区块 type:Block
        return:
            block_vali 合法标识 type:bool
        '''
        btemp = block
        target = btemp.blockhead.target
        hash = btemp.calculate_blockhash()
        if hash >= target:
            print(f'valid unsuccess because hash:{hash} and target:{target}')
            return False
        else:
            return True
