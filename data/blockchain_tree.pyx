# cython: language_level=3
# distutils: language=c++

import copy

from .block import Block as BaseBlock, BlockTreeSchema

from libc.stdint cimport uint64_t
from libcpp.vector cimport vector


cdef long long INVALID_NODE = -1


cdef class BlockchainTree:
    cdef dict _hash_index
    cdef list _hashes
    cdef list _names
    cdef list _miners
    cdef list _timestamps
    cdef list _contents
    cdef list _adversarial
    cdef list _genesis
    cdef list _sizes
    cdef list _blocks
    cdef object _schema
    cdef dict _extra_columns
    cdef vector[long long] _parents
    cdef vector[long long] _first_children
    cdef vector[long long] _last_children
    cdef vector[long long] _next_siblings
    cdef vector[long long] _heights
    cdef vector[vector[uint64_t]] _visibility
    cdef long long _head

    def __cinit__(self):
        self._hash_index = {}
        self._hashes = []
        self._names = []
        self._miners = []
        self._timestamps = []
        self._contents = []
        self._adversarial = []
        self._genesis = []
        self._sizes = []
        self._blocks = []
        self._schema = None
        self._extra_columns = {}
        self._head = INVALID_NODE

    cdef void _ensure_view(self, long long view_id):
        cdef vector[uint64_t] column
        while self._visibility.size() <= <size_t>(view_id >> 6):
            column = vector[uint64_t](self._parents.size(), 0)
            self._visibility.push_back(column)

    cdef bint _is_visible(self, long long view_id, long long node_id):
        cdef size_t word
        cdef uint64_t bit
        if node_id < 0 or node_id >= <long long>self._parents.size():
            return False
        word = <size_t>(view_id >> 6)
        if word >= self._visibility.size():
            return False
        bit = (<uint64_t>1) << (view_id & 63)
        return (self._visibility[word][node_id] & bit) != 0

    cdef bint _mark_visible(self, long long view_id, long long node_id):
        cdef size_t word = <size_t>(view_id >> 6)
        cdef uint64_t bit = (<uint64_t>1) << (view_id & 63)
        cdef bint changed
        self._ensure_view(view_id)
        changed = (self._visibility[word][node_id] & bit) == 0
        self._visibility[word][node_id] |= bit
        return changed

    cdef long long _lookup(self, object blockhash):
        cdef object value = self._hash_index.get(blockhash)
        if value is None:
            return INVALID_NODE
        return <long long>value

    cdef long long _find_visible(self, long long view_id, object blockhash):
        cdef long long node_id = self._lookup(blockhash)
        if node_id == INVALID_NODE or not self._is_visible(view_id, node_id):
            return INVALID_NODE
        return node_id

    cdef object _block(self, long long node_id):
        if node_id == INVALID_NODE:
            return None
        return self._blocks[node_id]

    cdef long long _add_node(self, object block, long long parent_id) except -2:
        cdef long long node_id
        cdef object canonical
        cdef object schema
        cdef object record
        cdef object extra_values
        cdef object field_name
        cdef Py_ssize_t field_index
        cdef vector[uint64_t] column
        cdef size_t word

        schema = self._schema
        if schema is None:
            schema = BlockTreeSchema.from_block(block)
        node_id = self._lookup(block.blockhash)
        if node_id != INVALID_NODE:
            canonical = self._blocks[node_id]
            if block is canonical:
                return node_id
            if type(block) is not schema.block_type or type(block.blockhead) is not schema.blockhead_type:
                raise TypeError(
                    "all blocks in one BlockchainTree must use the schema bound by its genesis block")
            if self._parents[node_id] != parent_id:
                raise ValueError("block hash already exists with a different parent")
            if (self._names[node_id] != block.name or
                    self._heights[node_id] != block.height or
                    self._miners[node_id] != block.blockhead.miner or
                    self._timestamps[node_id] != block.blockhead.timestamp or
                    self._contents[node_id] != block.blockhead.content or
                    self._adversarial[node_id] != bool(block.isAdversaryBlock) or
                    self._genesis[node_id] != bool(block.isGenesis) or
                    self._sizes[node_id] != block.size):
                raise ValueError("block hash already exists with different immutable metadata")
            if schema.field_names:
                extra_values = schema.read_fields(block)
                for field_index, field_name in enumerate(schema.field_names):
                    if self._extra_columns[field_name][node_id] != extra_values[field_index]:
                        raise ValueError(
                            f"block hash already exists with different {field_name!r} metadata")
            return node_id

        record, extra_values = schema.read(block)

        if parent_id == INVALID_NODE:
            if not record.genesis:
                raise ValueError("only a genesis block may have no structural parent")
            if self._head != INVALID_NODE:
                raise ValueError("blockchain tree already has a genesis block")
        else:
            if record.parent_hash != self._hashes[parent_id]:
                raise ValueError("block prehash does not match the structural parent")
            if record.height != self._heights[parent_id] + 1:
                raise ValueError("block height does not follow the structural parent")

        canonical = copy.deepcopy(block)
        canonical.parentblock = self._block(parent_id)
        canonical.next = []
        record, extra_values = schema.read(canonical)
        if self._schema is None:
            self._schema = schema
            self._extra_columns = {name: [] for name in schema.field_names}
        node_id = <long long>self._parents.size()
        self._hash_index[record.blockhash] = node_id
        self._hashes.append(record.blockhash)
        self._names.append(record.name)
        self._miners.append(record.miner)
        self._timestamps.append(record.timestamp)
        self._contents.append(record.content)
        self._adversarial.append(record.adversarial)
        self._genesis.append(record.genesis)
        self._sizes.append(record.size)
        self._blocks.append(canonical)
        for field_index, field_name in enumerate(schema.field_names):
            self._extra_columns[field_name].append(extra_values[field_index])
        self._parents.push_back(parent_id)
        self._first_children.push_back(INVALID_NODE)
        self._last_children.push_back(INVALID_NODE)
        self._next_siblings.push_back(INVALID_NODE)
        self._heights.push_back(canonical.height)
        for word in range(self._visibility.size()):
            self._visibility[word].push_back(0)

        if parent_id == INVALID_NODE:
            self._head = node_id
        else:
            if self._first_children[parent_id] == INVALID_NODE:
                self._first_children[parent_id] = node_id
            else:
                self._next_siblings[self._last_children[parent_id]] = node_id
            self._last_children[parent_id] = node_id
        return node_id

    cdef long long _common_ancestor(self, long long left, long long right):
        while left != INVALID_NODE and self._heights[left] > self._heights[right]:
            left = self._parents[left]
        while right != INVALID_NODE and self._heights[right] > self._heights[left]:
            right = self._parents[right]
        while left != right:
            if left == INVALID_NODE or right == INVALID_NODE:
                return INVALID_NODE
            left = self._parents[left]
            right = self._parents[right]
        return left


cdef class PathSnapshot:
    cdef BlockchainTree _tree
    cdef vector[long long] _nodes

    def __len__(self):
        return self._nodes.size()

    @property
    def hashes(self):
        return tuple(self._tree._hashes[self._nodes[i]] for i in range(self._nodes.size()))

    @property
    def names(self):
        return tuple(self._tree._names[self._nodes[i]] for i in range(self._nodes.size()))

    @property
    def heights(self):
        return tuple(self._tree._heights[self._nodes[i]] for i in range(self._nodes.size()))

    @property
    def miners(self):
        return tuple(self._tree._miners[self._nodes[i]] for i in range(self._nodes.size()))

    @property
    def timestamps(self):
        return tuple(self._tree._timestamps[self._nodes[i]] for i in range(self._nodes.size()))

    @property
    def adversarial(self):
        return tuple(self._tree._adversarial[self._nodes[i]] for i in range(self._nodes.size()))

    @property
    def contents(self):
        return tuple(self._tree._contents[self._nodes[i]] for i in range(self._nodes.size()))

    @property
    def blocks(self):
        return tuple(self._tree._block(self._nodes[i]) for i in range(self._nodes.size()))

    @property
    def field_names(self):
        return () if self._tree._schema is None else self._tree._schema.field_names

    def field(self, name):
        cdef object column = self._tree._extra_columns.get(name)
        if column is None:
            raise KeyError(name)
        return tuple(column[self._nodes[i]] for i in range(self._nodes.size()))


cdef class TreeSnapshot:
    cdef BlockchainTree _tree
    cdef vector[long long] _nodes
    cdef vector[long long] _parent_indices
    cdef vector[long long] _child_offsets
    cdef vector[long long] _child_indices

    def __len__(self):
        return self._nodes.size()

    @property
    def hashes(self):
        return tuple(self._tree._hashes[self._nodes[i]] for i in range(self._nodes.size()))

    @property
    def names(self):
        return tuple(self._tree._names[self._nodes[i]] for i in range(self._nodes.size()))

    @property
    def heights(self):
        return tuple(self._tree._heights[self._nodes[i]] for i in range(self._nodes.size()))

    @property
    def miners(self):
        return tuple(self._tree._miners[self._nodes[i]] for i in range(self._nodes.size()))

    @property
    def timestamps(self):
        return tuple(self._tree._timestamps[self._nodes[i]] for i in range(self._nodes.size()))

    @property
    def adversarial(self):
        return tuple(self._tree._adversarial[self._nodes[i]] for i in range(self._nodes.size()))

    @property
    def genesis(self):
        return tuple(self._tree._genesis[self._nodes[i]] for i in range(self._nodes.size()))

    @property
    def sizes(self):
        return tuple(self._tree._sizes[self._nodes[i]] for i in range(self._nodes.size()))

    @property
    def contents(self):
        return tuple(self._tree._contents[self._nodes[i]] for i in range(self._nodes.size()))

    @property
    def parent_indices(self):
        return tuple(self._parent_indices[i] for i in range(self._parent_indices.size()))

    @property
    def child_offsets(self):
        return tuple(self._child_offsets[i] for i in range(self._child_offsets.size()))

    @property
    def child_indices(self):
        return tuple(self._child_indices[i] for i in range(self._child_indices.size()))

    @property
    def field_names(self):
        return () if self._tree._schema is None else self._tree._schema.field_names

    def field(self, name):
        cdef object column = self._tree._extra_columns.get(name)
        if column is None:
            raise KeyError(name)
        return tuple(column[self._nodes[i]] for i in range(self._nodes.size()))


cdef class VisibleBlockMapping:
    cdef Chain _chain

    def __len__(self):
        return self._chain._visible_count

    def __contains__(self, blockhash):
        return self._chain._tree._find_visible(self._chain._view_id, blockhash) != INVALID_NODE

    def __getitem__(self, blockhash):
        cdef long long node_id = self._chain._tree._find_visible(self._chain._view_id, blockhash)
        if node_id == INVALID_NODE:
            raise KeyError(blockhash)
        return self._chain._tree._block(node_id)

    def get(self, blockhash, default=None):
        cdef long long node_id = self._chain._tree._find_visible(self._chain._view_id, blockhash)
        if node_id == INVALID_NODE:
            return default
        return self._chain._tree._block(node_id)

    def keys(self):
        return self._chain.collect_visible_tree().hashes

    def values(self):
        cdef TreeSnapshot snapshot = self._chain.collect_visible_tree()
        return tuple(self._chain._tree._block(snapshot._nodes[i]) for i in range(snapshot._nodes.size()))

    def items(self):
        cdef TreeSnapshot snapshot = self._chain.collect_visible_tree()
        return tuple((self._chain._tree._hashes[snapshot._nodes[i]], self._chain._tree._block(snapshot._nodes[i]))
                     for i in range(snapshot._nodes.size()))

    def __iter__(self):
        return iter(self.keys())


cdef class ChainFactory:
    cdef BlockchainTree _tree
    cdef long long _next_view_id

    def __cinit__(self):
        self._tree = BlockchainTree()
        self._next_view_id = 0

    cdef Chain _new_chain(self, object miner_id):
        cdef Chain chain = Chain.__new__(Chain)
        chain._initialize(self, self._next_view_id, miner_id)
        self._next_view_id += 1
        self._tree._ensure_view(chain._view_id)
        return chain

    def create(self, miner_id=None):
        return self._new_chain(miner_id)

    @property
    def schema(self):
        return self._tree._schema

    def clone(self, Chain source, miner_id=None):
        cdef Chain target
        cdef size_t node_id
        if source._factory is not self:
            raise ValueError("source chain belongs to a different factory")
        if miner_id is None:
            miner_id = source._miner_id
        target = self._new_chain(miner_id)
        for node_id in range(source._tree._parents.size()):
            if source._tree._is_visible(source._view_id, node_id):
                if source._tree._mark_visible(target._view_id, node_id):
                    target._visible_count += 1
        target._head_id = source._head_id
        target._tip_id = source._tip_id
        return target


cdef class Chain:
    cdef ChainFactory _factory
    cdef BlockchainTree _tree
    cdef long long _view_id
    cdef object _miner_id
    cdef long long _head_id
    cdef long long _tip_id
    cdef long long _visible_count
    cdef object _switch_callback
    cdef object _merge_callback
    cdef object _merge_tracker_callback
    cdef VisibleBlockMapping _block_mapping

    def __cinit__(self):
        self._view_id = INVALID_NODE
        self._head_id = INVALID_NODE
        self._tip_id = INVALID_NODE
        self._visible_count = 0
        self._switch_callback = None
        self._merge_callback = None
        self._merge_tracker_callback = None

    def __init__(self, miner_id=None, factory=None):
        if self._view_id != INVALID_NODE:
            return
        if factory is None:
            factory = ChainFactory()
        if not isinstance(factory, ChainFactory):
            raise TypeError("factory must be a ChainFactory")
        self._initialize(factory, factory._next_view_id, miner_id)
        factory._next_view_id += 1
        self._tree._ensure_view(self._view_id)

    cdef void _initialize(self, ChainFactory factory, long long view_id, object miner_id):
        self._factory = factory
        self._tree = factory._tree
        self._view_id = view_id
        self._miner_id = miner_id
        self._head_id = INVALID_NODE
        self._tip_id = INVALID_NODE
        self._visible_count = 0
        self._switch_callback = None
        self._merge_callback = None
        self._merge_tracker_callback = None
        self._block_mapping = VisibleBlockMapping.__new__(VisibleBlockMapping)
        self._block_mapping._chain = self

    cdef long long _visible_id(self, object block):
        if block is None:
            return INVALID_NODE
        return self._tree._find_visible(self._view_id, block.blockhash)

    cdef long long _ingest_visible(self, object block, long long parent_id) except -2:
        cdef long long node_id = self._tree._add_node(block, parent_id)
        if self._tree._mark_visible(self._view_id, node_id):
            self._visible_count += 1
        if self._head_id == INVALID_NODE and self._tree._parents[node_id] == INVALID_NODE:
            self._head_id = node_id
        return node_id

    cdef void _switch_tip(self, long long node_id):
        self._tip_id = node_id
        if self._switch_callback is not None:
            self._switch_callback(self._tree._block(node_id))

    @property
    def view_id(self):
        return self._view_id

    @property
    def miner_id(self):
        return self._miner_id

    @miner_id.setter
    def miner_id(self, value):
        self._miner_id = value

    @property
    def head(self):
        return self._tree._block(self._head_id)

    @property
    def last_block(self):
        return self._tree._block(self._tip_id)

    @last_block.setter
    def last_block(self, block):
        self.set_last_block(block)

    @property
    def block_set(self):
        return self._block_mapping

    @property
    def schema(self):
        return self._tree._schema

    def search_block_by_hash(self, blockhash):
        cdef long long node_id = self._tree._find_visible(self._view_id, blockhash)
        return self._tree._block(node_id)

    def search_block(self, block):
        return self._tree._block(self._visible_id(block))

    def get_last_block(self):
        return self._tree._block(self._tip_id)

    def set_last_block(self, block):
        cdef long long node_id
        if block is not None and not isinstance(block, BaseBlock):
            raise TypeError("block must be a Block")
        node_id = self._visible_id(block)
        if node_id == INVALID_NODE:
            return None
        self._switch_tip(node_id)
        return None

    def get_height(self, block=None):
        if block is not None:
            return block.get_height()
        if self._tip_id == INVALID_NODE:
            return 0
        return self._tree._heights[self._tip_id]

    def add_blocks(self, blocks, insert_point=None, deepcopy=True):
        cdef list pending
        cdef object block
        cdef object existing
        cdef long long parent_id = INVALID_NODE
        cdef long long node_id = INVALID_NODE
        cdef long long old_tip
        if isinstance(blocks, list):
            if any(not isinstance(block, BaseBlock) for block in blocks):
                raise TypeError("blocks must contain only Block objects")
        elif not isinstance(blocks, BaseBlock):
            raise TypeError("blocks must be a Block or list of Block objects")
        if not blocks:
            return None
        if isinstance(blocks, list):
            pending = list(blocks)
        else:
            existing = self.search_block(blocks)
            if existing is not None:
                return existing
            pending = [blocks]

        if insert_point is not None:
            parent_id = self._visible_id(insert_point)
            if parent_id == INVALID_NODE:
                raise ValueError("insert_point is not visible in this chain")
        elif self._head_id != INVALID_NODE:
            parent_id = self._tree._find_visible(self._view_id, pending[-1].blockhead.prehash)
            if parent_id == INVALID_NODE:
                raise ValueError("parent block is not visible in this chain")

        while pending:
            block = pending[-1]
            existing = self.search_block(block)
            if existing is None:
                break
            parent_id = self._visible_id(existing)
            pending.pop()

        old_tip = self._tip_id
        while pending:
            block = pending.pop()
            if parent_id == INVALID_NODE and not block.isGenesis:
                raise ValueError("non-genesis block has no visible parent")
            node_id = self._ingest_visible(block, parent_id)
            parent_id = node_id

        if node_id == INVALID_NODE:
            return self._tree._block(parent_id)
        if self._merge_callback is not None:
            self._merge_callback(self._tree._block(node_id))
        if old_tip == INVALID_NODE or self._tree._heights[node_id] > self._tree._heights[old_tip]:
            self._switch_tip(node_id)
        return self._tree._block(node_id)

    def add_block_forcibly(self, block):
        cdef list path = []
        cdef set seen = set()
        cdef object current = block
        cdef object local
        if block is None:
            return None
        if not isinstance(block, BaseBlock):
            raise TypeError("block must be a Block")
        local = self.search_block(current)
        while current is not None and local is None:
            if current.blockhash in seen:
                raise ValueError("cycle in caller-provided block path")
            seen.add(current.blockhash)
            path.append(current)
            current = current.parentblock
            local = self.search_block(current)
        if local is None:
            return None
        if not path:
            return local
        return self.add_blocks(path, insert_point=local)

    def common_prefix(self, left, right):
        cdef long long left_id = self._visible_id(left)
        cdef long long right_id = self._visible_id(right)
        if left_id == INVALID_NODE or right_id == INVALID_NODE:
            return None
        return self._tree._block(self._tree._common_ancestor(left_id, right_id))

    def get_ancestor(self, block, distance=1):
        cdef long long node_id = self._visible_id(block)
        cdef long long remaining
        if not isinstance(distance, int) or distance < 0:
            raise ValueError("distance must be a non-negative integer")
        if node_id == INVALID_NODE:
            return None
        remaining = distance
        while remaining > 0 and node_id != INVALID_NODE:
            node_id = self._tree._parents[node_id]
            remaining -= 1
        return self._tree._block(node_id)

    def collect_ancestor_path(self, start, stop=None, include_start=True,
                              include_stop=True, reverse=False):
        cdef long long current = self._visible_id(start)
        cdef long long stop_id = self._visible_id(stop) if stop is not None else INVALID_NODE
        cdef PathSnapshot snapshot = PathSnapshot.__new__(PathSnapshot)
        cdef vector[long long] reversed_nodes
        cdef size_t i
        if current == INVALID_NODE:
            raise ValueError("start block is not visible in this chain")
        snapshot._tree = self._tree
        if not include_start:
            current = self._tree._parents[current]
        while current != INVALID_NODE:
            if current == stop_id:
                if include_stop:
                    snapshot._nodes.push_back(current)
                break
            snapshot._nodes.push_back(current)
            current = self._tree._parents[current]
        if stop is not None and current == INVALID_NODE:
            raise ValueError("stop block is not an ancestor of start")
        if reverse:
            for i in range(snapshot._nodes.size()):
                reversed_nodes.push_back(snapshot._nodes[snapshot._nodes.size() - i - 1])
            snapshot._nodes.swap(reversed_nodes)
        return snapshot

    def collect_visible_tree(self):
        cdef TreeSnapshot snapshot = TreeSnapshot.__new__(TreeSnapshot)
        cdef vector[long long] local_indices
        cdef long long node_id
        cdef long long child
        cdef long long parent
        cdef size_t index
        cdef size_t cursor = 0
        snapshot._tree = self._tree
        local_indices.assign(self._tree._parents.size(), INVALID_NODE)
        if self._head_id == INVALID_NODE:
            snapshot._child_offsets.push_back(0)
            return snapshot
        snapshot._nodes.push_back(self._head_id)
        local_indices[self._head_id] = 0
        while cursor < snapshot._nodes.size():
            node_id = snapshot._nodes[cursor]
            child = self._tree._first_children[node_id]
            while child != INVALID_NODE:
                if self._tree._is_visible(self._view_id, child):
                    local_indices[child] = <long long>snapshot._nodes.size()
                    snapshot._nodes.push_back(child)
                child = self._tree._next_siblings[child]
            cursor += 1
        for index in range(snapshot._nodes.size()):
            node_id = snapshot._nodes[index]
            parent = self._tree._parents[node_id]
            snapshot._parent_indices.push_back(
                INVALID_NODE if parent == INVALID_NODE else local_indices[parent])
            snapshot._child_offsets.push_back(snapshot._child_indices.size())
            child = self._tree._first_children[node_id]
            while child != INVALID_NODE:
                if self._tree._is_visible(self._view_id, child):
                    snapshot._child_indices.push_back(local_indices[child])
                child = self._tree._next_siblings[child]
        snapshot._child_offsets.push_back(snapshot._child_indices.size())
        return snapshot

    def InversShowBlock(self):
        cdef PathSnapshot snapshot = self.collect_ancestor_path(self.last_block)
        return list(snapshot.blocks)

    def ShowBlock(self):
        cdef TreeSnapshot snapshot = self.collect_visible_tree()
        cdef list blocks = [self._tree._block(snapshot._nodes[i]) for i in range(snapshot._nodes.size())]
        print("".join(f"{block.name};" for block in blocks))
        return blocks

    def ShowLChain(self):
        blocks = self.InversShowBlock()
        blocks.reverse()
        print("".join(f"{block.name}→→→→" for block in blocks))
        return blocks

    def set_switch_tracker_callback(self, callback):
        self._switch_callback = callback

    def set_merge_tracker_callback(self, callback):
        self._merge_tracker_callback = callback

    def set_merge_callback(self, callback):
        self._merge_callback = callback

    def __deepcopy__(self, memo):
        cdef Chain cloned = self._factory.clone(self)
        memo[id(self)] = cloned
        return cloned

    def __reduce__(self):
        cdef TreeSnapshot snapshot = self.collect_visible_tree()
        from .chain import _restore_snapshot_chain
        blocks = [copy.deepcopy(self._tree._block(snapshot._nodes[i]))
                  for i in range(snapshot._nodes.size())]
        tip_hash = None if self._tip_id == INVALID_NODE else self._tree._hashes[self._tip_id]
        return _restore_snapshot_chain, (self._miner_id, blocks, tip_hash)

    def ShowStructure1(self):
        from .chain import show_structure
        return show_structure(self)

    def ShowStructure(self, miner_num=10):
        from .chain import plot_structure
        return plot_structure(self, miner_num)

    def ShowStructureWithGraphviz(self, other_list=None):
        from .chain import render_graphviz
        return render_graphviz(self, other_list)

    def GetBlockIntervalDistribution(self):
        from .chain import plot_intervals
        return plot_intervals(self)

    def printchain2txt(self, chain_data_url="chain_data.txt"):
        from .chain import printchain2txt
        return printchain2txt(self, chain_data_url)

    def CalculateStatistics(self, rounds, honest_miners, adver_ids, confirm_delay,
                            dataitem_params, valid_dataitems, quantile,
                            eclipsed_ids=None, chain_switch_events=None):
        from .chain import calculate_statistics
        return calculate_statistics(
            self, rounds, honest_miners, adver_ids, confirm_delay,
            dataitem_params, valid_dataitems, quantile, eclipsed_ids)
