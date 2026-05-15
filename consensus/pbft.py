import random
from enum import Enum

import global_var
from .consensus_abc import Consensus
from data import Message, BlockCarrier
from external import common_prefix
from functions import hash_bytes, BYTE_ORDER, INT_LEN

import logging

logger = logging.getLogger(__name__)

class PBFTStage(Enum):
    PRE_PREPARE = 1
    PREPARE = 2
    COMMIT = 3

class PBFT(Consensus):
    class BlockHead(Consensus.BlockHead):
        __slots__ = ['view_id']
        def __init__(self, preblock: Consensus.Block = None, timestamp=0, content=b'',
                     miner_id=-1, view_id=0):
            super().__init__(preblock, timestamp, content, miner_id)
            self.view_id = view_id

        def __eq__(self, value):
            if not isinstance(value, PBFT.BlockHead):
                return False
            return super().__eq__(value) and value.view_id == self.view_id

        def calculate_blockhash(self) -> bytes:
            data = self.miner.to_bytes(INT_LEN, BYTE_ORDER, signed=True) + \
                   self.view_id.to_bytes(INT_LEN, BYTE_ORDER, signed=False) + \
                   self.content + self.prehash + \
                   self.timestamp.to_bytes(INT_LEN, BYTE_ORDER, signed=False)
            return hash_bytes(data).digest()

    class ConsensusMsg(Message, BlockCarrier):
        def __init__(self, block:Consensus.Block, view_id, consensus_stage:PBFTStage, 
                     sig_nodeid, size: float = 2):
            digest = block.blockhash
            digest_hex = digest.hex() if isinstance(digest, (bytes, bytearray)) else str(digest)
            name = f"PBFT-{consensus_stage.name}-{digest_hex}-{sig_nodeid}"
            super().__init__(name, size)
            self.digest = block.blockhash # hash value of block
            self.block:PBFT.Block = block
            self.view_id = view_id
            self.consensus_stage = consensus_stage
            self.sig_nodeid = sig_nodeid # id of the node signing the message

        def __repr__(self):
            return f"PBFTMsg(stage={self.consensus_stage.name}, block={self.block.name}, view={self.view_id}, sig_node={self.sig_nodeid})"
        
        def get_block(self) -> Consensus.Block:
            if self.consensus_stage == PBFTStage.PRE_PREPARE:
                return self.block
            else:
                return None

    class MsgBuffer():
        def __init__(self, view) -> None:
            self.view_id = view
            self.preprepare_msg:PBFT.ConsensusMsg = None
            self.prepare_msg:list[PBFT.ConsensusMsg] = []
            self.commit_msg:list[PBFT.ConsensusMsg] = []
            self.committed = False

    class LocalState(Enum):
        COMMITTED_LOCAL = 1
        BLOCK_RECEIVED = 2
        PREPARED = 3

    def __init__(self, miner_id, consensus_param:dict):
        super().__init__(miner_id)
        self.blocktime = int(consensus_param['blocktime'])
        # primary node waits for 'blocktime' rounds before generating new block
        self.fault_tolerance = int(consensus_param['fault_tolerance'])
        # maximal faulty or malicious node
        self.view_id = int(consensus_param['initial_view'])
        self.local_state = PBFT.LocalState.COMMITTED_LOCAL
        self.send_buffer:list[Message] = []
        self.msg_buffer:dict[bytes,PBFT.MsgBuffer] = {}
        self.round_counter = 0

    def is_primary(self, miner_id):
        return self.view_id % global_var.get_miner_num() == miner_id

    def is_prepared(self, digest):
        prepare_register = dict.fromkeys(range(global_var.get_miner_num()), 0)
        for msg in self.msg_buffer[digest].prepare_msg:
            prepare_register[msg.sig_nodeid] += 1
        prepare_count = global_var.get_miner_num() - list(prepare_register.values()).count(0)
        for node, count in prepare_register.items():
            if count > 1:
                logger.warning('prepare message from node %d duplicates', node)
        return prepare_count >= 2*self.fault_tolerance

    def is_committed_local(self, digest):
        commit_register = dict.fromkeys(range(global_var.get_miner_num()), 0)
        for msg in self.msg_buffer[digest].commit_msg:
            commit_register[msg.sig_nodeid] += 1
        commit_count = global_var.get_miner_num() - list(commit_register.values()).count(0)
        for node, count in commit_register.items():
            if count > 1:
                logger.warning('commit message from node %d duplicates', node)
        return commit_count >= 2*self.fault_tolerance + 1

    def setparam(self, **consensus_params):
        self.blocktime = int(consensus_params.get('blocktime') or self.blocktime)
        fault_tolerance = consensus_params.get('fault_tolerance', self.fault_tolerance)
        self.fault_tolerance = int(fault_tolerance)
        self.view_id = int(consensus_params.get('initial_view') or self.view_id)

    def mining_consensus(self, miner_id:int, isadversary, x, round):
        last_block = self.local_chain.get_last_block()
        blockhead = self.BlockHead(last_block, round, x, miner_id, self.view_id)
        block = self.Block(blockhead, last_block, isadversary, global_var.get_blocksize())
        return block

    def consensus_process(self, isadversary, x, round):
        self.round_counter += 1
        if self.is_primary(self.miner_id):
            if self.local_state == PBFT.LocalState.COMMITTED_LOCAL and self.round_counter >= self.blocktime:
                newblock = self.mining_consensus(self.miner_id, isadversary, x, round)
                # self.local_chain.add_blocks(newblock, deepcopy=False)
                newblock.parentblock = self.local_chain.get_last_block()
                preprepare_msg = PBFT.ConsensusMsg(newblock, self.view_id, PBFTStage.PRE_PREPARE, \
                                                   self.miner_id, global_var.get_blocksize())
                self.resolve_preprepare_msg(preprepare_msg, send_prepare = False)
                logger.info('current primary node %d propose block %s', self.miner_id, newblock.name)
                self.round_counter = 0
                return [preprepare_msg], True
        if self.send_buffer:
            msg = self.send_buffer.pop(0)
            if isinstance(msg, PBFT.ConsensusMsg):
                logger.info('node %d send %s message confirming block %s', self.miner_id,
                            msg.consensus_stage.name, msg.block.name)
            return [msg], True
        return None, False
    
    def local_state_update(self, round):
        new_update = False
        chain_update = []
        forwarded_msgs = []
        original_last_block = None
        for msg in self.receive_tape:
            if not isinstance(msg, PBFT.ConsensusMsg):
                continue
            if not isinstance(msg.block, self.Block) or not isinstance(msg.block.blockhead, self.BlockHead):
                continue
            if msg.consensus_stage == PBFTStage.PRE_PREPARE:
                if self.resolve_preprepare_msg(msg):
                    forwarded_msgs.append(msg)
            if msg.consensus_stage == PBFTStage.PREPARE:
                if self.resolve_prepare_msg(msg):
                    forwarded_msgs.append(msg)
            if msg.consensus_stage == PBFTStage.COMMIT:
                committed_blocks, forward = self.resolve_commit_msg(msg)
                if forward:
                    forwarded_msgs.append(msg)
                if committed_blocks:
                    original_last_block = self.local_chain.last_block if original_last_block is None else original_last_block
                    new_update = True
        if new_update:
            blocktmp = self.local_chain.get_last_block()
            fork_point = common_prefix(blocktmp, original_last_block)
            while blocktmp.blockhash != fork_point.blockhash:
                chain_update.insert(0, blocktmp)
                blocktmp = blocktmp.parentblock
        return self.local_chain, chain_update, forwarded_msgs

    def blockheight_match(self, msg):
        '''对于从节点，判断PBFT消息中区块高度是否比本地链中的最新区块高1'''
        return msg.block.height == self.local_chain.get_last_block().height + 1

    def resolve_preprepare_msg(self, msg, send_prepare = True):
        self.msg_buffer.setdefault(msg.digest, PBFT.MsgBuffer(self.view_id))
        if self.local_state == PBFT.LocalState.COMMITTED_LOCAL and \
            self.msg_buffer[msg.digest].preprepare_msg is None and \
            msg.view_id == self.view_id and \
            msg.block.blockhead.view_id == msg.view_id and \
            msg.digest == msg.block.calculate_blockhash() and \
            self.valid_block(msg.block):
            self.msg_buffer[msg.digest].preprepare_msg = msg
            # send one prepare message for pre-prepare message 
            prepare_msg = PBFT.ConsensusMsg(msg.block, self.view_id, PBFTStage.PREPARE, \
                                            self.miner_id, global_var.get_blocksize())
            if send_prepare:
                self.send_buffer.append(prepare_msg)
                self.msg_buffer[msg.digest].prepare_msg.append(prepare_msg)
            self.local_state = PBFT.LocalState.BLOCK_RECEIVED
            return True # The message is valid and processed
        return False

    def resolve_prepare_msg(self, msg):
        self.msg_buffer.setdefault(msg.digest, PBFT.MsgBuffer(self.view_id))
        if msg.view_id == self.view_id and not self._has_sig(self.msg_buffer[msg.digest].prepare_msg, msg.sig_nodeid):
            if msg.digest != msg.block.calculate_blockhash() or not self.valid_block(msg.block):
                return False
            self.msg_buffer[msg.digest].prepare_msg.append(msg)
            if self.local_state == PBFT.LocalState.BLOCK_RECEIVED and \
                self.blockheight_match(msg) and self.is_prepared(msg.digest):
                commit_msg = PBFT.ConsensusMsg(msg.block, self.view_id, PBFTStage.COMMIT, \
                                               self.miner_id, global_var.get_blocksize())
                # reach prepared state once 2f valid prepare message collected
                self.local_state = PBFT.LocalState.PREPARED
                logger.info('node %d prepared block %s at height %d', self.miner_id, msg.block.name, msg.block.height)
                self.send_buffer.append(commit_msg)
                self.msg_buffer[msg.digest].commit_msg.append(commit_msg)
            return True # The message is valid and processed
        return False

    def resolve_commit_msg(self, msg):
        self.msg_buffer.setdefault(msg.digest, PBFT.MsgBuffer(self.view_id))
        if msg.view_id == self.view_id and not self._has_sig(self.msg_buffer[msg.digest].commit_msg, msg.sig_nodeid):
            if msg.digest != msg.block.calculate_blockhash() or not self.valid_block(msg.block):
                return None, False
            self.msg_buffer[msg.digest].commit_msg.append(msg)
            local_height = self.local_chain.get_height()
            if self.local_chain.search_block(msg.block) is not None:
                self.local_state = PBFT.LocalState.COMMITTED_LOCAL
                self.round_counter = 0
                self.msg_buffer[msg.digest].committed = True
                return None, True
            if self.msg_buffer[msg.digest].committed:
                return None, True
            if (self.local_state == PBFT.LocalState.PREPARED and \
                self.blockheight_match(msg) and \
                self.is_committed_local(msg.digest)) or \
                (msg.block.height > local_height+1 and \
                self.is_committed_local(msg.digest)):
                # reach commit_local state once 2f+1 valid commit message collected and prepared state reached
                # or reset local state and merge blocks once current lastblock fall behind other nodes by 2 blocks
                self.local_state = PBFT.LocalState.COMMITTED_LOCAL
                logger.info('node %d commit block %s at height %d', self.miner_id, msg.block.name, msg.block.height)
                self.round_counter = 0
                prehash = msg.block.blockhead.prehash
                # TODO handle chain reorganization or more than one block to merge
                if insert_point := self.local_chain.search_block_by_hash(prehash):
                    self.local_chain.add_blocks(blocks=[msg.block], insert_point=insert_point, deepcopy=False)
                    return [msg.block], True
            else:
                return None, True
        return None, False

    def valid_chain(self, lastblock: Consensus.Block):
        '''验证区块链是否PoW合法\n
        param:
            lastblock 要验证的区块链的最后一个区块 type:Block
        return:
            chain_vali 合法标识 type:bool
        '''
        chain_vali = True
        if chain_vali and lastblock:
            blocktmp = lastblock
            ss = blocktmp.calculate_blockhash()
            while chain_vali and blocktmp is not None:
                hash_val = blocktmp.calculate_blockhash()
                block_vali = self.valid_block(blocktmp)
                if block_vali and hash_val == ss:
                    ss = blocktmp.blockhead.prehash
                    blocktmp = blocktmp.parentblock
                else:
                    chain_vali = False
        return chain_vali

    def valid_block(self, block: Consensus.Block):
        if block is None or isinstance(block, self.Block) is False:
            return False
        if block.isGenesis:
            return True
        blockhead:PBFT.BlockHead = block.blockhead
        if isinstance(blockhead, self.BlockHead) is False:
            return False
        view_id = blockhead.view_id
        if view_id is None or view_id != self.view_id: # TODO need extra validation when implementing view change
            return False
        expected_primary = view_id % global_var.get_miner_num()
        if blockhead.miner != expected_primary:
            return False
        blockhead.calculate_blockhash()

        return True
    
    def receive_filter(self, msg: Message):
        if isinstance(msg, PBFT.ConsensusMsg):
            if msg.digest in self.msg_buffer:
                buf = self.msg_buffer[msg.digest]
                if msg is buf.preprepare_msg:
                    return False
                if msg.consensus_stage == PBFTStage.PREPARE and \
                    self._has_sig(buf.prepare_msg, msg.sig_nodeid):
                    return False
                if msg.consensus_stage == PBFTStage.COMMIT and \
                    self._has_sig(buf.commit_msg, msg.sig_nodeid):
                    return False
            self.receive_tape.append(msg)
            random.shuffle(self.receive_tape)
            return True
        return False

    @staticmethod
    def _has_sig(msg_list:list["PBFT.ConsensusMsg"], sig_nodeid:int) -> bool:
        return any(m.sig_nodeid == sig_nodeid for m in msg_list)
