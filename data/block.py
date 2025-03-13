import copy
from itertools import chain
from abc import ABCMeta, abstractmethod

from functions import BYTE_ORDER, INT_LEN, hash_bytes

from .message import Message


class BlockHead(metaclass=ABCMeta):
    __slots__ = ['prehash', 'timestamp', 'content', 'miner']
    __omit_keys = {} # The items to omit when printing the object
    
    def __init__(self, prehash=b'', timestamp=0, content = b'', Miner = -1):
        self.prehash:bytes = prehash  # 前一个区块的hash
        self.timestamp:int = timestamp  # 时间戳
        self.content:bytes = content
        self.miner:int = Miner  # 矿工
    
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
        keys = chain.from_iterable(list(getattr(s, '__slots__', []) for s in self.__class__.__mro__) + list(getattr(self, '__dict__', {}).keys()))
        for k in keys:
            if k not in self.__omit_keys:
                v = getattr(self, k)
                bhlist.append(k + ': ' + (str(v) if not isinstance(v, bytes) else v.hex()))
        return '\n'.join(bhlist)


class Block(Message):
    __slots__ = ['__blockhead', 'height', 'blockhash', 'isAdversaryBlock', 'next', 'parentblock', 'isGenesis']
    __omit_keys = {'segment_num'} # The items to omit when printing the object

    def __init__(self, name=None, blockhead: BlockHead = None, height = None, 
                 isadversary=False, isgenesis=False, blocksize_MB=2):
        super().__init__(name, blocksize_MB)
        self.__blockhead = blockhead
        self.height = height
        self.blockhash = blockhead.calculate_blockhash()
        self.isAdversaryBlock = isadversary
        self.next:list[Block] = []  # 子块列表
        self.parentblock:Block = None  # 母块
        self.isGenesis = isgenesis
        # super().__init__(int(random.uniform(0.5, 2)))
        # 单位:MB 随机 0.5~1 MB
        
    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result

        slots = chain.from_iterable((getattr(s, '__slots__', [])) for s in self.__class__.__mro__)
        for k in slots:
            if cls.__name__ == 'Block':
                if k == 'next':
                    setattr(result, k, [])
                    continue
                if k == 'parentblock':
                    setattr(result, k, None)
                    continue
            if k == '__name':
                key = '_Message__name'
            elif k == '__blockhead':
                key = '_Block__blockhead'
            else:
                key = k
            setattr(result, key, copy.deepcopy(getattr(self, key), memo))

        if var_dict := getattr(self, '__dict__', None):
            for k, v in var_dict.items():
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
        
        slots = chain.from_iterable(getattr(s, '__slots__', []) for s in self.__class__.__mro__)
        var_dict = {}
        for k in slots:
            if k == '__name':
                key = '_Message__name'
            elif k == '__blockhead':
                key = '_Block__blockhead'
            else:
                key = k
            var_dict[k] = getattr(self, key)

        if hasattr(self, '__dict__'):
            var_dict.update(self.__dict__)
        var_dict.update({'next': [b.name for b in self.next if self.next], 
                      'parentblock': self.parentblock.name if self.parentblock is not None else None})
        for omk in self.__omit_keys:
            if omk in var_dict:
                del var_dict[omk]
        return '\n'+ _formatter(var_dict)

    @property
    def blockhead(self):
        return self.__blockhead

    def calculate_blockhash(self):
        self.blockhash = self.blockhead.calculate_blockhash()
        return self.blockhash

    def get_height(self):
        return self.height