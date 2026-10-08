'''
AtomizationBehaviorGroup.py
用于定义攻击者的行为
'''
import attack.attack_type._atomization_behavior as aa
import consensus
import global_var
import miner.miner as miner
import network
from data import Block, Chain
from consensus.consensus_abc import Consensus
from external import I
from miner._consts import OUTER, SELF,FLOODING,SELFISH,SPEC_TARGETS


class AtomizationBehavior(aa.AtomizationBehavior):

    def renew(self, miner_list:list[miner.Miner], honest_chain_prp: Chain, honest_chain_vt:list[Chain], round, eclipse_list_ids:list[int] = None):
        # 更新adversary中的所有区块链状态：基准链 矿工状态(包括输入和其自身链 )
        mine_input = 0
        newest_block_prp = honest_chain_prp.get_last_block()
        newest_block_prps = []
        newest_blocks_vt = []
        for i, vtchain_update_chain in enumerate(honest_chain_vt):
            newest_vtblock = vtchain_update_chain.get_last_block()
            newest_blocks_vt.append(newest_vtblock)
        imcoming_block_from_eclipse:dict[any,Block] = {}
        if eclipse_list_ids is not None:
            for temp_miner in miner_list:
                remove_block:dict[str,Block] = {}
                for i,incoming_block in enumerate(temp_miner.consensus._receive_tape_tx):
                    if not isinstance(incoming_block, Consensus.Block):
                        continue
                    if incoming_block.blockhead.miner in eclipse_list_ids:
                        remove_block[incoming_block.blockhash] = incoming_block
                for k,block in remove_block.items():
                    imcoming_block_from_eclipse[block.blockhash] = block
                    temp_miner.consensus._receive_tape_tx.remove(block)
                for i,incoming_block in enumerate(temp_miner.consensus._receive_tape_prp):
                    if not isinstance(incoming_block, Consensus.Block):
                        continue
                    if incoming_block.blockhead.miner in eclipse_list_ids:
                        remove_block[incoming_block.blockhash] = incoming_block
                for k,block in remove_block.items():
                    imcoming_block_from_eclipse[block.blockhash] = block
                    temp_miner.consensus._receive_tape_prp.remove(block)
                for i,incoming_block in enumerate(temp_miner.consensus._receive_tape_vt):
                    if not isinstance(incoming_block, Consensus.Block):
                        continue
                    if incoming_block.blockhead.miner in eclipse_list_ids:
                        remove_block[incoming_block.blockhash] = incoming_block
                for k,block in remove_block.items():
                    imcoming_block_from_eclipse[block.blockhash] = block
                    temp_miner.consensus._receive_tape_vt.remove(block)

        for temp_miner in miner_list:
            prpchain_update, update_index, vtchain_update = temp_miner.consensus.local_state_update()
            # print('in prpchain_update:')
            # for block in prpchain_update.block_set.values():
            #     print(f'{block.name}')
            mine_input = max(mine_input,I(round, temp_miner.input_tape)) # 模拟诚实矿工的BBP--输入
            # 如果存在更新将更新的区块添加到基准链上
            prpchain_update:Chain
            if prpchain_update.get_height()>=newest_block_prp.get_height():
                height = prpchain_update.get_height()
                for block in prpchain_update.block_set.values():
                    if block.height == height:
                        newest_block_prps.append(block)
                # newest_block_prp = prpchain_update.get_last_block()
            for i, vt_chain in enumerate(vtchain_update):
                if vt_chain.get_height() >= newest_blocks_vt[i].get_height():
                    newest_blocks_vt[i] = vt_chain.get_last_block()
        if newest_block_prps != []:
            pass
        else :
            newest_block_prps = [newest_block_prp]
        for newest_block_prp in newest_block_prps:
            newest_block_prp = honest_chain_prp._add_block_forcibly(block=newest_block_prp)
            for temp_miner in miner_list:
                temp_miner.consensus.local_chain_prp._add_block_forcibly(block=newest_block_prp)

        for i, honest_vtchain in enumerate(honest_chain_vt):
            newest_blocks_vt[i] = honest_vtchain._add_block_forcibly(block=newest_blocks_vt[i])
        for temp_miner in miner_list:
            for i, local_vtchain in enumerate(temp_miner.consensus.local_chain_vt):
                local_vtchain._add_block_forcibly(block=newest_blocks_vt[i])


        mine_input:any
        if eclipse_list_ids is not None:
            return newest_block_prp, mine_input,imcoming_block_from_eclipse
        else:
            return newest_block_prp, mine_input

    def clear(self, miner_list:list[miner.Miner]) -> None:
        # clear the input tape and communcation tape
        # 清除矿工的input tape和communication tape
        for temp_miner in miner_list:
            temp_miner.clear_tapes()
            # temp_miner.input_tape = []  # clear the input tape
            # temp_miner._consensus._receive_tape = []  # clear the communication tape

    def adopt(self, honest_chain: Chain, adver_chain: Chain) -> Block:
        # Adversary adopts the newest chain based on the adver's chains
        adver_chain._add_block_forcibly(block=honest_chain.get_last_block())
        # 首先将attack内的adver_chain更新为attacker可以接收到的最新的链
        fork_block = adver_chain.get_last_block()
        return fork_block

    def adopt_fail_after_doublespending(self, honest_chain: Chain, adver_chain: Chain) -> Block:
        # Adversary adopts the newest chain based on the adver's chains
        aaa, vtonprps = adver_chain._add_block_forcibly_fail_doublespending(block=honest_chain.get_last_block())
        # 首先将attack内的adver_chain更新为attacker可以接收到的最新的链
        fork_block = adver_chain.get_last_block()
        return fork_block, vtonprps

    def wait(self) -> None:
        # Adversary waits, and do nothing in current round.
        pass

    def upload(self, network: network.Network, adver_chain_prp: Chain, adver_chain_vt: list[Chain],
               current_miner: miner.Miner, round, miner_list: list[miner.Miner], fork_block: list[Block] = [],
               strategy=FLOODING, forward_target: list = None, upload_statement=None) -> list[Block]:
        # 初始化 upload_block_list，包含所有区块的列表
        print(f'fork_block:{fork_block}')
        upload_block_list = []
        print('has fork block:')
        for block in fork_block:
            print(f'{block.name}')
        # 根据 fork_block 确定对应的链并添加区块
        for block in fork_block:
            if block.index is not None:
                if block.index != 0:
                    if block.index == 1:
                        cur = adver_chain_prp.get_last_block()
                    elif block.index > 1:
                        cur = adver_chain_vt[block.index - 2].get_last_block()

                    upload_block_list.append(cur)

                    while cur is not None and cur.blockhash != block.blockhash:
                        cur = cur.parentblock
                        if cur is not None:
                            upload_block_list.append(cur)
        print('now uplaod list has')
        for block in upload_block_list:
            print(f'{block.name}')


        # 对所有矿工进行 forward 操作
        for adver_miner in miner_list:
            if adver_miner.miner_id != current_miner.miner_id:
                adver_miner.forward(upload_block_list, SELF, strategy=strategy, spec_targets=forward_target)
            else:
                adver_miner.forward(upload_block_list, SELF, strategy=strategy, spec_targets=forward_target)
            # 保证 adver_miner 一定会收到
            for block in upload_block_list:
                adver_miner.consensus.receive_block(block)
                if block.index == 1:
                    adver_miner.consensus.local_chain_prp.add_blocks(blocks=block)
                elif block.index > 1:
                    adver_miner.consensus.local_chain_vt[block.index - 2].add_blocks(blocks=block)

        return upload_block_list

    def upload_ds(self, network: network.Network, adver_chain_prp: Chain, adver_chain_vt: list[Chain],
                  global_chain_prp: Chain, global_chain_vt: list[Chain],
               current_miner: miner.Miner, round, miner_list: list[miner.Miner], fork_block: list[Block] = [],
               strategy=FLOODING, forward_target: list = None, upload_statement=None, index = 0 ) -> list[Block]:
        # 初始化 upload_block_list，包含所有区块的列表
        print('in upload doublespending success')
        print(f'fork_block:{fork_block}')
        upload_block_list = []
        print('has fork block:')
        for block in fork_block:
            if block.index is None:
                index_ds = index
            else:
                index_ds = block.index
            print(f'{block.name} in index {index_ds}')
        # 根据 fork_block 确定对应的链并添加区块
        for block in fork_block:
            if block.index is None:
                index_ds = index
            else:
                index_ds = block.index
            if index_ds is not None:
                if index_ds != 0:
                    if index_ds == 1:
                        cur = adver_chain_prp.get_last_block()
                    elif index_ds > 1:
                        cur = adver_chain_vt[index_ds - 2].get_last_block()

                    # Genesis blocks are already shared by every chain. A genesis
                    # block has index=None, so it must not enter the upload list.
                    if cur is not None and not cur.isGenesis:
                        upload_block_list.append(cur)

                    while cur is not None and cur.blockhash != block.blockhash:
                        cur = cur.parentblock
                        if cur is not None and not cur.isGenesis:
                            upload_block_list.append(cur)
        print('now uplaod list has')
        for block in upload_block_list:
            block_index = block.index
            print(f'{block.name} in index {block_index}')

            if block_index is None:
                if block.isGenesis:
                    continue
                raise ValueError(f'Non-genesis block {block.name} has no chain index')

            if block_index == 1:
                global_prp_height = global_chain_prp.last_block.height
                if block.height > global_prp_height:
                    global_chain_prp.set_last_block(block)
            elif block_index > 1:
                voter_position = block_index - 2
                if voter_position >= len(global_chain_vt):
                    raise IndexError(f'Invalid voter chain index: {block_index}')

                global_vt_height = global_chain_vt[voter_position].last_block.height
                if block.height > global_vt_height:
                    global_chain_vt[voter_position].set_last_block(block)
                    print(f'global_chain_vt{voter_position} now has last block {block}')


        # 对所有矿工进行 forward 操作
        for adver_miner in miner_list:
            if adver_miner.miner_id != current_miner.miner_id:
                adver_miner.forward(upload_block_list, SELF, strategy=strategy, spec_targets=forward_target)
            else:
                adver_miner.forward(upload_block_list, SELF, strategy=strategy, spec_targets=forward_target)
            # 保证 adver_miner 一定会收到
            for block in upload_block_list:
                adver_miner.consensus.receive_block(block)
                if block.index == 1:
                    adver_miner.consensus.local_chain_prp.add_blocks(blocks=block)
                elif block.index > 1:
                    adver_miner.consensus.local_chain_vt[block.index - 2].add_blocks(blocks=block)

        return upload_block_list

    def mine(self, miner_list:list[miner.Miner],current_miner: miner.Miner,
             miner_input: any, adver_chain_prp: Chain, global_chain_prp: Chain,
             adver_chain_vt: list[Chain], global_chain_vt: list[Chain],
             consensus: consensus.Consensus, round:int, necessary_blocks:list[Block]) ->  tuple[bool, Block]:
        # 以下是attack模块攻击者挖矿部分的思路及原因
        # 这里注意到如果调用 miner 自身的 mining 函数, 其使用的是 miner 自身的链以及 miner 自身的 q
        # 因此为了能方便后续使用者便于书写attack模块, 在 attack 模块中的初始化部分替换 miner 的这两部分内容
        # 特别提醒： Miner_ID 和 isAdversary 部分是 Environment 初始化已经设置好的, input 在 renew 部分也处理完毕
        #self.atlog['current_miner'] = self.current_miner.Miner_ID
        adm_newblock, mine_success = consensus.mining_consensus(
                miner_id = current_miner.miner_id, isadversary=True, x=miner_input, round=round, miner = current_miner, necessary_blocks=necessary_blocks)
        attack_mine: bool = False
        if adm_newblock:
            #self.atlog['block_content'] = adm_newblock.blockhead.content
            attack_mine = True
            print(f'get adver block{adm_newblock.name} and mined by {adm_newblock.blockhead.miner}, worked by {current_miner.miner_id}, timestamp: {adm_newblock.blockhead.timestamp}')
            # if len(miner_list) == 1:
            #     adm_newblock = miner_list[0].consensus.local_chain.add_blocks(adm_newblock)
            # 自己挖出来的块直接用AddBlock即可
            # adm_newblock = adver_chain.add_blocks(blocks=adm_newblock)

            # adver_chain.set_last_block(adm_newblock)
            # adver_chain.last_block = adm_newblock
            # 作为历史可能分叉的一部添加到全局链中
            # global_chain._add_block_forcibly(adm_newblock)
            # for temp_miner in miner_list:
            #     # 将新挖出的区块放在攻击者的receive_tape
            #     temp_miner._consensus._receive_tape.append(adm_newblock)

            if adm_newblock.index == 0:
                global_var.rec_tx()
                tx = global_var.get_txnum()
                global_var.set_arrive_time(f"TX{tx}", round)
                global_var.set_arrive_time_tx(f"TX{tx}", round)
                global_var.add_tx(f"TX{tx}")
            elif adm_newblock.index == 1:
                # current_miner.consensus.prpBlockchain.ShowStructure1()
                global_var.set_arrive_time_prp(adm_newblock.name, round)
                adm_newblock = adver_chain_prp.add_blocks(blocks=adm_newblock)
                adver_chain_prp.set_last_block(adm_newblock)
                if global_var.get_attack_execute_type() == 'DoubleSpending':
                    # print(f'add before:{adm_newblock.blockhead.timestamp}')
                    global_chain_prp._add_block_forcibly_ds(adm_newblock)
                    # print(f'add after:{adm_newblock.blockhead.timestamp}')
                else:
                    global_chain_prp._add_block_forcibly(adm_newblock)  # 作为历史可能分叉的一部添加到全局链中
                # for temp_miner in miner_list:
                #     if temp_miner.Miner_ID != current_miner.Miner_ID:
                #         temp_miner.consensus.receive_tape_prp.append(adm_newblock)
                    # 将新挖出的区块放在攻击者的receive_tape
            elif adm_newblock.index < (global_var.get_vtnum() + 2):
                adm_newblock = adver_chain_vt[adm_newblock.index-2].add_blocks(blocks=adm_newblock)
                # print(f'has add block{adm_newblock.name} to adver chain vt{adm_newblock.index-2}{adver_chain_vt[adm_newblock.index-2].miner_id}')
                adver_chain_vt[adm_newblock.index-2].set_last_block(adm_newblock)
                if global_var.get_attack_execute_type() == 'DoubleSpending':
                    global_chain_vt[adm_newblock.index-2]._add_block_forcibly_ds(adm_newblock)
                else:
                    global_chain_vt[adm_newblock.index-2]._add_block_forcibly(adm_newblock)  # 作为历史可能分叉的一部添加到全局链中
        adm_newblock: Block
        return attack_mine, adm_newblock
