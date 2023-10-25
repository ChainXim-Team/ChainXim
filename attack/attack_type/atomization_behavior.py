'''
AtomizationBehaviorGroup.py
用于定义攻击者的行为
'''
import attack.attack_type._atomization_behavior as aa
from external import I
import miner, chain, network, consensus
class AtomizationBehavior(aa.AtomizationBehavior):

    def renew(self, miner_list:list[miner.Miner], honest_chain: chain.Chain, round) -> (chain.Block, any):
        # 更新adversary中的所有区块链状态：基准链 矿工状态(包括输入和其自身链 )
        mine_input = 0
        for temp_miner in miner_list:
            chain_update, update_index = temp_miner.consensus.maxvalid() 
            mine_input = I(round, temp_miner.input_tape) # 模拟诚实矿工的BBP--输入
            chain_update : chain.Chain
            honest_chain.add_block_copy(chain_update.lastblock) # 如果存在更新将更新的区块添加到基准链上 
            #self.local_record.add_block_copy(chain_update.lastblock) # 同时 也将该区块同步到全局链上
        newest_block = honest_chain.lastblock
        newest_block:chain.Block
        mine_input:any
        return newest_block, mine_input

    def clear(self, miner_list:list[miner.Miner]) -> None:
        # clear the input tape and communcation tape
        # 清除矿工的input tape和communication tape
        for temp_miner in miner_list:
            temp_miner.input_tape = []  # clear the input tape
            temp_miner.consensus.receive_tape = []  # clear the communication tape

    def adopt(self, honest_chain: chain.Chain, adver_chain: chain.Chain) -> chain.Block:
        # Adversary adopts the newest chain based on tthe adver's chains
        adver_chain.add_block_copy(honest_chain.lastblock)
        # 首先将attack内的adver_chain更新为attacker可以接收到的最新的链
        fork_block = adver_chain.lastblock
        fork_block:chain.Block
        return fork_block

    def wait(self) -> None:
        # Adversary waits, and do nothing in current round.
        pass

    def upload(self, network_type: network.Network, adver_chain: chain.Chain, \
               current_miner: miner.Miner, round) -> chain.Block:
        # acceess to network
        network_type.access_network([adver_chain.lastblock], current_miner.Miner_ID, round)
        upload_block = adver_chain.lastblock
        upload_block: chain.Block
        return upload_block

    def mine(self, miner_list:list[miner.Miner],current_miner: miner.Miner, miner_input: any, \
             adver_chain: chain.Chain, global_chain: chain.Chain, \
                consensus: consensus.Consensus) -> (bool, chain.Block):
        # 以下是attack模块攻击者挖矿部分的思路及原因
        # 这里注意到如果调用 miner 自身的 mining 函数, 其使用的是 miner 自身的链以及 miner 自身的 q 
        # 因此为了能方便后续使用者便于书写attack模块, 在 attack 模块中的初始化部分替换 miner 的这两部分内容
        # 特别提醒： Miner_ID 和 isAdversary 部分是 Environment 初始化已经设置好的, input 在 renew 部分也处理完毕
        #self.atlog['current_miner'] = self.current_miner.Miner_ID
        adm_newblock, mine_success = consensus.mining_consensus(\
            Miner_ID=current_miner.Miner_ID, isadversary=True, x=miner_input)
        attack_mine = False
        if adm_newblock:
            #self.atlog['block_content'] = adm_newblock.blockhead.content
            attack_mine = True
            adver_chain.add_block_direct(adm_newblock)  # 自己挖出来的块直接用AddBlock即可
            adver_chain.lastblock = adm_newblock
            global_chain.add_block_copy(adm_newblock) # 作为历史可能分叉的一部添加到全局链中
            for temp_miner in miner_list:
                temp_miner.consensus.receive_tape.append(adm_newblock)
                # 将新挖出的区块放在攻击者的receive_tape
        attack_mine: bool
        adm_newblock: chain.Block
        return attack_mine, adm_newblock