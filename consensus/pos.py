import json
from typing import Dict

import global_var
from external import common_prefix
from functions import BYTE_ORDER, HASH_LEN, INT_LEN, hash_bytes

from .consensus_abc import Consensus

import logging
logger = logging.getLogger(__name__)

class PoS(Consensus):

    class BlockHead(Consensus.BlockHead):
        """适用于PoS共识协议的区块头"""
        __slots__ = ['target', 'stake', 'staketime']

        def __init__(self, preblock: Consensus.Block = None, timestamp=0, content=b'', miner_id=-1,
                     target=(2**(8*HASH_LEN) - 1).to_bytes(HASH_LEN, BYTE_ORDER), stake=None,
                     staketime=None):
            super().__init__(preblock, timestamp, content, miner_id)
            self.target = target  # 难度目标，不参与哈希
            self.stake = stake or {}
            self.staketime = staketime or {}

        def __eq__(self, value):
            return (super().__eq__(value) and self.target == value.target and
                    self.stake == value.stake and self.staketime == value.staketime)

        def calculate_blockhash(self) -> bytes:
            data = PoS._kernel_hash_input(self.prehash, self.timestamp, self.content, self.miner,
                                          self.stake, self.staketime)
            return hash_bytes(data).digest()

    class Block(Consensus.Block):
        __slots__ = ['consumed_coinage']

        def __init__(self, blockhead: Consensus.BlockHead, preblock: Consensus.Block = None,
                     isadversary=False, blocksize_MB=2, consumed_coinage: int = 0):
            super().__init__(blockhead, preblock, isadversary, blocksize_MB)
            self.consumed_coinage = consumed_coinage

    def __init__(self, miner_id, consensus_params: dict):
        self.target = bytes.fromhex(consensus_params['target'])
        self.stake = self._build_stake(consensus_params)
        self.stake_serialized = self._serialize_dict(self.stake)
        self.q = self.stake.get(miner_id, 0)
        self.precompute_threshold = consensus_params.get('precompute_threshold', 0) # prevent precompute attack
        super().__init__(miner_id=miner_id)

    def create_genesis_block(self, chain, blockheadextra: dict = None, blockextra: dict = None):
        genesis_staketime = {i: 0 for i in self.stake}
        genesis_blockhead = self.BlockHead(None, 0, b'', -1, self.target, dict(self.stake),
                                           genesis_staketime)
        genesis_block = self.Block(genesis_blockhead, None, False, global_var.get_blocksize(),
                                   consumed_coinage=0)
        chain.add_blocks(blocks=genesis_block)

    def _build_stake(self, consensus_params: dict) -> Dict[int, int]:
        q_distr = consensus_params['q_distr']
        if q_distr == 'equal':
            return {i: consensus_params['q_ave'] for i in range(global_var.get_miner_num())}
        if isinstance(q_distr, list):
            return {i: q_distr[i] for i in range(len(q_distr))}
        raise ValueError("q_distr should be a list or the string 'equal'")

    @staticmethod
    def _serialize_dict(d: Dict[int, int]) -> bytes:
        return json.dumps(d, sort_keys=True, separators=(',', ':')).encode()

    @staticmethod
    def _kernel_hash_input(prehash: bytes, timestamp: int, content:bytes, miner_id: int,
                           stake: Dict[int, int] | bytes, staketime: Dict[int, int]) -> bytes:
        stake_bytes = stake if isinstance(stake, (bytes, bytearray)) else PoS._serialize_dict(stake)
        return (
            prehash +
            timestamp.to_bytes(INT_LEN, BYTE_ORDER, signed=True) +
            content +
            miner_id.to_bytes(INT_LEN, BYTE_ORDER, signed=True) +
            stake_bytes +
            PoS._serialize_dict(staketime)
        )

    def setparam(self, **consensus_params):
        """
        设置pos参数,主要是target
        """
        self.target = bytes.fromhex(consensus_params.get('target') or self.target)

    def mining_consensus(self, miner_id: bytes, isadversary, x, round):
        """计算PoS"""
        pos_success = False
        b_last = self.local_chain.last_block
        prehash = b_last.blockhash
        miner_id_int = int.from_bytes(miner_id, BYTE_ORDER, signed=True)

        parent_staketime = b_last.blockhead.staketime
        coinage = round - parent_staketime.get(miner_id_int, 0)
        staketime = dict(parent_staketime)
        staketime[miner_id_int] = round
        if coinage <= 0:
            return (None, pos_success)

        kernel_input = self._kernel_hash_input(prehash, round, x, miner_id_int,
                               self.stake_serialized, parent_staketime)
        kernel_hash = hash_bytes(kernel_input).digest()
        target_value = int.from_bytes(self.target, BYTE_ORDER)
        max_hash = (1 << (8 * HASH_LEN)) - 1
        threshold = min(target_value * coinage, max_hash)

        if kernel_hash < int.to_bytes(threshold, HASH_LEN, BYTE_ORDER):
            pos_success = True
            consumed_coinage = b_last.consumed_coinage + coinage
            blockhead = self.BlockHead(b_last, round, x, miner_id_int, self.target,
                                       dict(self.stake), staketime)
            blocknew = self.Block(blockhead, b_last, isadversary, global_var.get_blocksize(),
                                  consumed_coinage=consumed_coinage)
            return (blocknew, pos_success)
        return (None, pos_success)

    def local_state_update(self, round):
        new_update = False
        chain_update = []
        tree_update = []
        original_last_block = None
        for incoming_block in self.receive_tape:
            if not isinstance(incoming_block, self.Block):
                continue
            if self.precompute_threshold > 0 and \
               abs(incoming_block.blockhead.timestamp - round) > self.precompute_threshold:
                continue
            prehash = incoming_block.blockhead.prehash
            insert_point = self.local_chain.search_block_by_hash(prehash)
            if insert_point is None:
                self.block_buffer.setdefault(prehash, [])
                self.block_buffer[prehash].append(incoming_block)
                continue
            if not self.valid_block(incoming_block, parent=insert_point):
                continue
            conj_block = self.local_chain.add_blocks(blocks=[incoming_block], insert_point=insert_point,
                                                     deepcopy=False, auto_switch=False)
            fork_tip, touched_blocks = self.synthesize_fork(conj_block)
            tree_update.extend(touched_blocks)
            current_coinage = self.local_chain.last_block.consumed_coinage
            incoming_block_coinage = fork_tip.consumed_coinage
            if current_coinage < incoming_block_coinage:
                original_last_block = self.local_chain.last_block if original_last_block is None else original_last_block
                self.local_chain.set_last_block(fork_tip)
                new_update = True

        if new_update:
            blocktmp = self.local_chain.get_last_block()
            fork_point = common_prefix(blocktmp, original_last_block)
            while blocktmp.blockhash != fork_point.blockhash:
                chain_update.insert(0, blocktmp)
                blocktmp = blocktmp.parentblock
        return self.local_chain, chain_update, tree_update

    def valid_block(self, block: Consensus.Block, parent: Consensus.Block = None):
        if block.isGenesis:
            return True

        parent = parent or block.parentblock
        if parent is None:
            parent = self.local_chain.search_block_by_hash(block.blockhead.prehash)
        if parent is None:
            logger.warning("Block validation failed: parent block not found.")
            return False

        if block.blockhead.timestamp <= parent.blockhead.timestamp:
            logger.warning("Block validation failed: timestamp not greater than parent.")
            return False

        if block.blockhead.stake != parent.blockhead.stake:
            logger.warning("Block validation failed: stake mismatch.")
            return False

        miner_id = block.blockhead.miner
        if miner_id not in block.blockhead.staketime:
            logger.warning("Block validation failed: miner_id not in staketime.")
            return False

        for mid, st in parent.blockhead.staketime.items():
            expected = block.blockhead.timestamp if mid == miner_id else st
            if block.blockhead.staketime.get(mid) != expected:
                logger.warning(f"Block validation failed: staketime mismatch for miner {mid}.")
                return False

        coinage = block.blockhead.timestamp - parent.blockhead.staketime.get(miner_id, 0)
        if coinage <= 0:
            logger.warning("Block validation failed: coinage <= 0.")
            return False

        kernel_input = self._kernel_hash_input(
            block.blockhead.prehash,
            block.blockhead.timestamp,
            block.blockhead.content,
            block.blockhead.miner,
            self.stake_serialized,
            parent.blockhead.staketime
        )
        kernel_hash = hash_bytes(kernel_input).digest()
        target_value = int.from_bytes(block.blockhead.target, BYTE_ORDER)
        max_hash = (1 << (8 * HASH_LEN)) - 1
        if kernel_hash >= int.to_bytes(min(target_value * coinage, max_hash), HASH_LEN, BYTE_ORDER):
            logger.warning("Block validation failed: kernel hash above threshold.")
            return False

        expected_consumed = parent.consumed_coinage + coinage
        if block.consumed_coinage != expected_consumed:
            logger.warning("Block validation failed: consumed_coinage mismatch.")
            return False

        return True
