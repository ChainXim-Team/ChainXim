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
from miner._consts import OUTER_RCV_MSG, SELF_GEN_MSG,FLOODING,SELFISH,SPEC_TARGETS

class AtomizationBehavior(aa.AtomizationBehavior):

    def renew(self, adver_list:list[miner.Miner], honest_chain: Chain, round, eclipse_list_ids:list[int] = None):
        # 更新adversary中的所有区块链状态：基准链 矿工状态(包括输入和其自身链 )
        mine_input = 0
        newest_block = honest_chain.get_last_block()

        imcoming_block_from_eclipse:dict[any,Block] = {}
        # 根据消息来源确认coming block的上一跳
        if eclipse_list_ids is not None:
            for temp_miner in adver_list:
                remove_block:dict[str,Block] = {}
                
                for i,incoming_packet in enumerate(temp_miner._NIC._receive_buffer):
                    
                    if incoming_packet.source in eclipse_list_ids and isinstance(incoming_packet.payload, network.DataSegment):
                        # 如果是消息片段 判断片段来源 根据来源标记该区块
                        remove_block[incoming_packet.payload.origin_block.blockhash] = incoming_packet.payload.origin_block
                        continue
                    if incoming_packet.source in eclipse_list_ids and isinstance(incoming_packet.payload, Block):
                        # 如果是消息区块 判断区块来源 根据来源标记该区块
                        remove_block[incoming_packet.payload.blockhash] = incoming_packet.payload
                
                for k,block in remove_block.items():
                    # 将从日蚀节点来源的区块记录下来
                    imcoming_block_from_eclipse[block.blockhash] = block

                    # 从攻击节点的准进消息中剔除对应标记区块 防止二次处理
                    if block in set(temp_miner.consensus.receive_tape):
                        temp_miner.consensus.receive_tape.remove(block)

            
        input_tape = []
        for temp_miner in adver_list:
            chain_update, update_index = temp_miner.consensus.local_state_update() 
            input_tape.extend(temp_miner.input_tape) # 模拟诚实矿工的BBP--输入
            # 如果存在更新将更新的区块添加到基准链上   
            chain_update:Chain
            if chain_update.get_height()>=newest_block.get_height():
                newest_block = chain_update.get_last_block()

        # 检测最新区块是否是来源于eclipse miner
        flag = True
        if len(imcoming_block_from_eclipse)>0:
            temp_newest = newest_block
            while not honest_chain.search_block(temp_newest):
                #     # 如果最新区块来源于日蚀节点 且 在adver_chain上出现了
                #     # 从逻辑上不需要更新到honest chain上
                if newest_block.isAdversaryBlock:
                    flag = False
                    break
                temp_newest = temp_newest.parentblock
        if flag:
            newest_block = honest_chain._add_block_forcibly(block=newest_block)

        for temp_miner in adver_list:
            temp_miner.consensus.local_chain._add_block_forcibly(block=newest_block)
        mine_input:bytes = I(round, input_tape)
        if eclipse_list_ids is not None:
            return newest_block, mine_input, imcoming_block_from_eclipse
        else:
            return newest_block, mine_input

    def clear(self, adver_list:list[miner.Miner]) -> None:
        # clear the input tape and communcation tape
        # 清除矿工的input tape和communication tape
        for temp_miner in adver_list:
            temp_miner.clear_tapes()

    def adopt(self, honest_chain: Chain, adver_chain: Chain) -> Block:
        # Adversary adopts the newest chain based on tthe adver's chains
        adver_chain._add_block_forcibly(block=honest_chain.get_last_block())
        # 首先将attack内的adver_chain更新为attacker可以接收到的最新的链
        fork_block = adver_chain.get_last_block()
        return fork_block

    def wait(self) -> None:
        # Adversary waits, and do nothing in current round.
        pass

    def upload(self,  adver_chain: Chain,
               current_miner: miner.Miner, round, adver_list: list[miner.Miner], fork_block: Block = None,
               strategy = FLOODING, forward_target:list = None, syncLocalChain = False) -> Block:
        # 强制向所有攻击者的邻居发送攻击者链
        # network.access_network([adver_chain.last_block], current_miner.miner_id, round)

        upload_block_list = [adver_chain.get_last_block()]
        # upload_block_list 不能有重复元素 必须是有前指关系 item0->item1->item2->....
        # 寻找fork_block 和 adver_chain的最近公共祖先 优化上传数量
        # 记录寻找公共祖先过程中的区块 作为上传列表
        # 这个列表的子集一定是其余矿工未收到的区块
        # 该列表是包含子集且不至于缺少区块个数的最小集合

        if fork_block != None and upload_block_list[0].blockhash != fork_block.blockhash: 
            cur = upload_block_list[0].parentblock
            while (cur != None and fork_block != None and cur.blockhash != fork_block.blockhash and cur.height > fork_block.height):
                upload_block_list.append(cur)
                cur = cur.parentblock
                while fork_block != None and fork_block.height >= cur.height and cur.blockhash != fork_block.blockhash:
                    fork_block = fork_block.parentblock

        
        if len(upload_block_list) > 20:
            flag = True

        # upload_block = adver_chain.get_last_block()
        # miner_list
        if strategy == FLOODING:
            adver_list[0].forward(upload_block_list, SELF_GEN_MSG, forward_strategy =strategy, spec_targets=forward_target)
            for adver_miner in adver_list:
                # '''保证adverminer一定会收到'''
                adver_miner.consensus.local_chain._add_block_forcibly(adver_chain.get_last_block())
        elif strategy == "SPEC_TARGETS":
            neighbors = {}
            for target in forward_target:
                neighbors[target] = set()
            for i,adver_miner in enumerate(adver_list):
                for nb in adver_miner.neighbors:
                    if nb in neighbors and len(neighbors[nb])<1:
                        neighbors[nb].add(i)
            for target in forward_target:
                adver_list[neighbors[target].pop()].forward(upload_block_list, SELF_GEN_MSG, forward_strategy = SPEC_TARGETS, spec_targets=forward_target)
        # upload_block: Block
        return upload_block_list

    def mine(self, adver_list: list[miner.Miner], current_miner: miner.Miner, 
             miner_input: any, adver_chain: Chain,  
             consensus: consensus.Consensus, round:int) ->  tuple[bool, Block]:
        # 以下是attack模块攻击者挖矿部分的思路及原因
        # 这里注意到如果调用 miner 自身的 mining 函数, 其使用的是 miner 自身的链以及 miner 自身的 q 
        # 因此为了能方便后续使用者便于书写attack模块, 在 attack 模块中的初始化部分替换 miner 的这两部分内容
        # 特别提醒： Miner_ID 和 _isAdversary 部分是 Environment 初始化已经设置好的, input 在 renew 部分也处理完毕
        #self.atlog['current_miner'] = self.current_miner.Miner_ID
        adm_newblock, mine_success = consensus.mining_consensus(
                miner_id = current_miner.consensus.miner_id_bytes, isadversary=True, x=miner_input, round=round)
        attack_mine: bool = False
        if adm_newblock:
            #self.atlog['block_content'] = adm_newblock.blockhead.content
            attack_mine = True
            # if len(miner_list) == 1:
            #     adm_newblock = miner_list[0].consensus.local_chain.add_blocks(adm_newblock)
            # 自己挖出来的块直接用AddBlock即可
            adm_newblock = adver_chain.add_blocks(blocks=adm_newblock)

            adver_chain.set_last_block(adm_newblock)
            # adver_chain.last_block = adm_newblock
            # 作为历史可能分叉的一部添加到全局链中
            # global_chain._add_block_forcibly(adm_newblock)
            # for temp_miner in miner_list:
            #     # 将新挖出的区块放在攻击者的receive_tape
            #     temp_miner._consensus.receive_tape.append(adm_newblock)

        adm_newblock: Block
        return attack_mine, adm_newblock