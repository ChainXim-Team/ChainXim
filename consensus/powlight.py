import global_var
import random
from .pow import PoW


class PoWlight(PoW):

    class BlockHead(PoW.BlockHead):
        '''适用于PoW共识协议的区块头'''
        __slots__ = ['target', 'nonce']
        def __init__(self, preblock: PoW.Block = None, timestamp=0, content=0, miner_id=-1,
                     target = 0, nonce = 0):
            # currently content is an integer equal to the round the block is generated
            super().__init__(preblock, timestamp, content, miner_id)
            self.target = target  # 难度目标
            self.nonce = nonce  # 随机数

        def calculate_blockhash(self) -> bytes:
            data = self.nonce
            return data

    def __init__(self,miner_id,consensus_params:dict):
        super().__init__(miner_id,consensus_params)
        self.ctr=0 #计数器
        self.target = int(consensus_params['target'],16)    
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
        self.target = int(consensus_params.get('target') or self.target, 16)            
        self.q = consensus_params.get('q') or self.q

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
        pow_success = False
        #print("mine",Blockchain)
        b_last = self.local_chain.get_last_block()#链中最后一个块
        
        random_float = random.random()
        target_value = 1 - (1 - self.target/2**256)**self.q
        if random_float < target_value:
            pow_success = True
            self.ctr = random_float
            blockhead = PoWlight.BlockHead(b_last, round, x, miner_id, self.target, self.ctr)
            blocknew = PoWlight.Block(blockhead, b_last, isadversary, global_var.get_blocksize())
            return (blocknew, pow_success)
        return (None, pow_success)

    def valid_block(self,block:PoW.Block):
        '''
        验证单个区块是否PoW合法\n
        param:
            block 要验证的区块 type:Block
        return:
            block_vali 合法标识 type:bool
        '''
        btemp = block
        nonce = btemp.blockhead.calculate_blockhash()
        if nonce >= 1 - (1 - self.target/2**256)**self.q:
            return False
        else:
            return True