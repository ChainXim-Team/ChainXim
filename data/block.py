import copy
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from itertools import chain
from typing import ClassVar, NamedTuple

from functions import BYTE_ORDER, INT_LEN, hash_bytes

from .message import Message


class BlockTreeRecord(NamedTuple):
    blockhash: bytes
    parent_hash: bytes
    name: str
    height: int
    miner: int
    timestamp: int
    content: bytes
    adversarial: bool
    genesis: bool
    size: float


@dataclass(frozen=True, slots=True)
class TreeField:
    name: str
    owner: str
    attribute: str
    value_type: type | tuple[type, ...]

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("tree field name must be a non-empty string")
        if self.owner not in {"block", "blockhead"}:
            raise ValueError("tree field owner must be 'block' or 'blockhead'")
        if not isinstance(self.attribute, str) or not self.attribute:
            raise ValueError("tree field attribute must be a non-empty string")

    def read(self, block):
        owner = block if self.owner == "block" else block.blockhead
        value = getattr(owner, self.attribute)
        if not isinstance(value, self.value_type):
            raise TypeError(
                f"tree field {self.name!r} must be {self.value_type}, "
                f"got {type(value)}"
            )
        try:
            hash(value)
        except TypeError as error:
            raise TypeError(f"tree field {self.name!r} must be immutable") from error
        return value


@dataclass(frozen=True, slots=True)
class BlockTreeSchema:
    block_type: type
    blockhead_type: type
    fields: tuple[TreeField, ...]
    field_names: tuple[str, ...] = dataclass_field(init=False)

    CORE_FIELDS: ClassVar[frozenset[str]] = frozenset({
        "blockhash", "parent_hash", "name", "height", "miner", "timestamp",
        "content", "adversarial", "genesis", "size",
    })

    def __post_init__(self):
        fields = tuple(self.fields)
        names = [field.name for field in fields]
        if len(names) != len(set(names)):
            raise ValueError("tree field names must be unique")
        if self.CORE_FIELDS.intersection(names):
            raise ValueError("custom tree fields cannot replace core fields")
        object.__setattr__(self, "fields", fields)
        object.__setattr__(self, "field_names", tuple(names))

    @staticmethod
    def _declared_fields(value_type, owner):
        fields = []
        for base in reversed(value_type.__mro__):
            for field in base.__dict__.get("__tree_fields__", ()):
                if not isinstance(field, TreeField):
                    raise TypeError("__tree_fields__ must contain TreeField objects")
                if field.owner != owner:
                    raise ValueError(
                        f"{value_type.__name__} declares {field.name!r} for {field.owner}"
                    )
                fields.append(field)
        return fields

    @classmethod
    def from_block(cls, block):
        fields = cls._declared_fields(type(block), "block")
        fields.extend(cls._declared_fields(type(block.blockhead), "blockhead"))
        return cls(type(block), type(block.blockhead), tuple(fields))

    def read(self, block):
        if type(block) is not self.block_type or type(block.blockhead) is not self.blockhead_type:
            raise TypeError(
                "all blocks in one BlockchainTree must use the schema bound by its genesis block"
            )
        head = block.blockhead
        record = BlockTreeRecord(
            block.blockhash,
            head.prehash,
            block.name,
            block.height,
            head.miner,
            head.timestamp,
            head.content,
            bool(block.isAdversaryBlock),
            bool(block.isGenesis),
            block.size,
        )
        return record, self.read_fields(block)

    def read_fields(self, block):
        return tuple(field.read(block) for field in self.fields)


class BlockHead(metaclass=ABCMeta):
    __slots__ = ['content', 'miner', 'prehash', 'timestamp']
    __tree_fields__ = ()
    __omit_keys: ClassVar[set[str]] = set() # The items to omit when printing the object
    
    def __init__(self, prehash=b'', timestamp=0, content = b'', Miner = -1):
        self.prehash:bytes = prehash  # 前一个区块的hash
        self.timestamp:int = timestamp  # 时间戳
        self.content:bytes = content
        self.miner:int = Miner  # 矿工

    def __eq__(self, value):
        if not isinstance(value, BlockHead):
            return False
        return self.prehash == value.prehash and \
               self.timestamp == value.timestamp and \
               self.content == value.content and \
               self.miner == value.miner
    
    @abstractmethod
    def calculate_blockhash(self) -> bytes:
        '''
        计算区块的hash
        return:
            hash type:bytes
        '''
        data = self.miner.to_bytes(INT_LEN, BYTE_ORDER,signed=True) + \
                self.content + \
                self.prehash
        return hash_bytes(data).digest()

    def __repr__(self) -> str:
        bhlist = []
        keys = chain.from_iterable(
            [getattr(base, '__slots__', []) for base in self.__class__.__mro__]
            + [getattr(self, '__dict__', {}).keys()]
        )
        for k in keys:
            if k not in self.__omit_keys:
                v = getattr(self, k)
                bhlist.append(k + ': ' + (str(v) if not isinstance(v, bytes) else v.hex()))
        return '\n'.join(bhlist)


class Block(Message):
    __slots__ = ['__blockhead', 'blockhash', 'height', 'isAdversaryBlock', 'isGenesis', 'next', 'parentblock']
    __tree_fields__ = ()
    __omit_keys: ClassVar[set[str]] = {'segment_num'} # The items to omit when printing the object

    def __init__(self, name, blockhead: BlockHead, height = None, 
                 isadversary=False, isgenesis=False, blocksize_MB=2):
        super().__init__(name, blocksize_MB)
        self.__blockhead = blockhead
        self.height = height
        self.blockhash = blockhead.calculate_blockhash()
        self.isAdversaryBlock = isadversary
        self.next:list[Block] = []  # 子块列表
        self.parentblock:Block | None = None  # 母块
        self.isGenesis = isgenesis
        # super().__init__(int(random.uniform(0.5, 2)))
        # 单位:MB 随机 0.5~1 MB
        
    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result

        slots = chain.from_iterable((getattr(s, '__slots__', [])) for s in self.__class__.__mro__)
        for k in slots:
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
            var_dict.pop(omk, None)
        return '\n'+ _formatter(var_dict)

    def __eq__(self, value):
        if not isinstance(value, Block):
            return False
        return self.blockhead == value.blockhead

    @property
    def blockhead(self):
        return self.__blockhead

    def calculate_blockhash(self):
        self.blockhash = self.blockhead.calculate_blockhash()
        return self.blockhash

    def get_height(self):
        return self.height
