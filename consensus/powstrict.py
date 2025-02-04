import global_var

from .pow import PoW
from functions import HASH_LEN, BYTE_ORDER


class PoWstrict(PoW):
    '''严格限制哈希率的PoW实现'''
    class BlockHead(PoW.BlockHead):
        '''适用于PoW共识协议的区块头'''
        __slots__ = []
        def calculate_blockhash(self) -> bytes:
            return (2**(8*HASH_LEN) - 1).to_bytes(HASH_LEN, BYTE_ORDER)

    def __init__(self,miner_id,consensus_params:dict):
        super().__init__(miner_id,consensus_params)
        from .random_oracle import RandomOracleMining, RandomOracleVerifying, get_int_size, get_byteorder
        self.mining_oracle:RandomOracleMining = None
        self.verifying_oracle:RandomOracleVerifying = None
        self.INT_SIZE = get_int_size()
        self.BYTEORDER = get_byteorder()

    def set_random_oracle(self, mining_oracle, verifying_oracle):
        '''设置Random Oracle'''
        self.mining_oracle = mining_oracle
        self.verifying_oracle = verifying_oracle

    def mining_consensus(self, miner_id:int, isadversary, x, round):
        '''计算PoW\n
        param:
            Miner_ID 该矿工的ID type:int
            x 写入区块的内容 type:any
            qmax 最大hash计算次数 type:int
        return:
            newblock 挖出的新块 type:None(未挖出)/Block
            pow_success POW成功标识 type:Bool
        '''
        b_last = self.local_chain.get_last_block() #链中最后一个块
        blockhead = self.BlockHead(preblock=b_last, timestamp=round, content=x,
                                   miner_id=miner_id, target=self.target, nonce=self.ctr)
        while self.mining_oracle.get_current_calls() < self.q:
            blockhead.nonce = self.ctr
            blockhash = self.mining_oracle.hash(self.serialize_blockhead(blockhead))
            if blockhash is None: # Mining oracle is used up
                return None, False
            if blockhash < self.target:
                newblock = PoW.Block(blockhead, b_last, isadversary, global_var.get_blocksize())
                newblock.blockhash = blockhash
                self.ctr = 0
                return newblock, True
            self.ctr += 1
        
        return None, False

        # Update blockhash according to the blockhash

    def serialize_blockhead(self, blockhead: PoW.BlockHead) -> bytes:
        '''将区块序列化为字节流'''
        return blockhead.miner.to_bytes(self.INT_SIZE, self.BYTEORDER, signed=True)+ \
                blockhead.content.to_bytes(self.INT_SIZE, self.BYTEORDER)+ \
                blockhead.prehash + \
                blockhead.nonce.to_bytes(self.INT_SIZE, self.BYTEORDER)

    def valid_block(self, block:PoW.Block):
        # Update blockhash first
        block.blockhash = self.verifying_oracle.hash(self.serialize_blockhead(block.blockhead))
        if block.blockhash < self.target:
            return True
        return False
