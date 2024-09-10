import copy
from abc import ABCMeta, abstractmethod

from functions import BYTE_ORDER, INT_LEN, hash_bytes

from .message import Message


class BlockHead(metaclass=ABCMeta):
    
    __omit_keys = {} # The items to omit when printing the object
    
    def __init__(self, prehash=None, timestamp=None, content = None, Miner=None):
        self.prehash = prehash  # 前一个区块的hash
        self.timestamp = timestamp  # 时间戳
        self.content = content
        self.miner = Miner  # 矿工
    
    @abstractmethod
    def calculate_blockhash(self) -> bytes:
        '''
        计算区块的hash
        return:
            hash type:bytes
        '''
        data = self.miner.to_bytes(INT_LEN, BYTE_ORDER,signed=True) + \
                self.content.to_bytes(INT_LEN, BYTE_ORDER) + \
                self.prehash
        return hash_bytes(data).digest()

    def __repr__(self) -> str:
        bhlist = []
        for k, v in self.__dict__.items():
            if k not in self.__omit_keys:
                bhlist.append(k + ': ' + (str(v) if not isinstance(v, bytes) else v.hex()))
        return '\n'.join(bhlist)


class Block(Message):

    __omit_keys = {'segment_num'} # The items to omit when printing the object

    def __init__(self, name=None, blockhead: BlockHead = None, height = None, 
                 isadversary=False, isgenesis=False, blocksize_MB=2):
        self.name = name
        self._blockhead = blockhead
        self.height = height
        self.blockhash = blockhead.calculate_blockhash()
        self.isAdversaryBlock = isadversary
        self.next:list[Block] = []  # 子块列表
        self.parentblock:Block = None  # 母块
        self.isGenesis = isgenesis
        super().__init__(blocksize_MB)
        # super().__init__(int(random.uniform(0.5, 2)))
        # 单位:MB 随机 0.5~1 MB
        
    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if cls.__name__ == 'Block' and k != 'next' and k != 'parentblock':
                setattr(result, k, copy.deepcopy(v, memo))
            if cls.__name__ == 'Block' and k == 'next':
                setattr(result, k, [])
            if cls.__name__ == 'Block' and k == 'parentblock':
                setattr(result, k, None)
            if cls.__name__ != 'Block':
                setattr(result, k, copy.deepcopy(v, memo))
        return result

    
    def __repr__(self) -> str:
        def _formatter(d, mplus=1):
            m = max(map(len, list(d.keys()))) + mplus
            s = '\n'.join([k.rjust(m) + ': ' + 
                           _indenter(str(v) if not isinstance(v, bytes) 
                           else v.hex(), m+2) for k, v in d.items()])
            return s
        def _indenter(s, n=0):
            split = s.split("\n")
            indent = " "*n
            return ("\n" + indent).join(split)
        
        bdict = copy.deepcopy(self.__dict__)
        bdict.update({'next': [b.name for b in self.next if self.next], 
                      'parentblock': self.parentblock.name if self.parentblock is not None else None})
        for omk in self.__omit_keys:
            if omk in bdict:
                del bdict[omk]
        return '\n'+ _formatter(bdict)

    @property
    def blockhead(self):
        return self._blockhead

    def calculate_blockhash(self):
        self.blockhash = self.blockhead.calculate_blockhash()
        return self.blockhash

    def get_height(self):
        return self.height