import logging
import global_var

from .pow import PoW
from functions import HASH_LEN, BYTE_ORDER

logger = logging.getLogger(__name__)

class SolidPoW(PoW):
    '''严格限制哈希率的PoW实现'''
    class BlockHead(PoW.BlockHead):
        '''适用于PoW共识协议的区块头'''
        __slots__ = []
        def calculate_blockhash(self) -> bytes:
            return (2**(8*HASH_LEN) - 1).to_bytes(HASH_LEN, BYTE_ORDER)

    def __init__(self,miner_id,consensus_params:dict):
        super().__init__(miner_id,consensus_params)
        from .random_oracle import RandomOracleMining, RandomOracleVerifying
        self.mining_oracle:RandomOracleMining = None
        self.verifying_oracle:RandomOracleVerifying = None

    def set_random_oracle(self, mining_oracle, verifying_oracle):
        '''设置Random Oracle'''
        self.mining_oracle = mining_oracle
        self.verifying_oracle = verifying_oracle

    def mining_consensus(self, miner_id:bytes, isadversary, x, round):
        '''计算PoW\n
        param:
            Miner_ID 该矿工的ID type:int
            x 写入区块的内容 type:any
            qmax 最大hash计算次数 type:int
        return:
            newblock 挖出的新块 type:None(未挖出)/Block
            pow_success POW成功标识 type:Bool
        '''
        b_last = self.local_chain.last_block # 链中最后一个块
        
        blockhead_bytes = miner_id + x + b_last.blockhash
        while self.mining_oracle.get_current_calls() < self.q:
            blockhash = self.mining_oracle.hash(blockhead_bytes + self.ctr.to_bytes(self.INT_SIZE, self.BYTEORDER))
            if blockhash is None: # Mining oracle is used up
                return None, False
            if blockhash < self.target:
                blockhead = self.BlockHead(preblock=b_last, timestamp=round, content=x,
                                           miner_id=int.from_bytes(miner_id, self.BYTEORDER, signed=True), target=self.target, nonce=self.ctr)
                newblock = PoW.Block(blockhead, b_last, isadversary, global_var.get_blocksize())
                newblock.blockhash = blockhash
                self.ctr = 0
                return newblock, True
            self.ctr += 1
        
        return None, False

    def serialize_blockhead(self, blockhead: PoW.BlockHead) -> bytes:
        '''将区块序列化为字节流'''
        return blockhead.miner.to_bytes(self.INT_SIZE, self.BYTEORDER, signed=True)+ \
                blockhead.content + blockhead.prehash + \
                blockhead.nonce.to_bytes(self.INT_SIZE, self.BYTEORDER)

    def valid_chain(self, lastblock):
        '''验证区块链是否PoW合法\n
        param:
            lastblock 要验证的区块链的最后一个区块 type:Block
        return:
            chain_vali 合法标识 type:bool
        '''
        chain_vali = False
        if lastblock:
            blocktmp = lastblock
            if blocktmp.blockhead.miner == self.miner_id:
                chain_vali = self.valid_block_self(blocktmp)
            else:
                chain_vali = self.valid_block(blocktmp)
            ss = blocktmp.blockhash
            while chain_vali and blocktmp is not None:
                if blocktmp.blockhead.miner == self.miner_id:
                    block_vali = self.valid_block_self(blocktmp)
                else:
                    block_vali = self.valid_block(blocktmp)
                if block_vali and blocktmp.blockhash == ss:
                    ss = blocktmp.blockhead.prehash
                    blocktmp = blocktmp.parentblock
                else:
                    chain_vali = False
        return chain_vali

    def valid_block_self(self, block:PoW.Block):
        # validate whether the block is really mined by the miner
        block_local = self.local_chain.search_block(block)
        blockhead_local = self.serialize_blockhead(block_local.blockhead)
        blockhead_incoming = self.serialize_blockhead(block.blockhead)
        if blockhead_local == blockhead_incoming and block.blockhash < self.target or block_local.isGenesis:
            return True
        else:
            return False

    def valid_block(self, block:PoW.Block):
        # Update blockhash first
        block.blockhash = self.verifying_oracle.hash(self.serialize_blockhead(block.blockhead))
        if block.blockhash is None:
            logger.error("Miner %d somehow verifying its own block: %s", block.blockhead.miner, str(block))
            return False
        if block.blockhash < self.target:
            return True
        return False
