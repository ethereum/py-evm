import pytest

from hypothesis import (
    given,
    strategies as st,
)

import rlp
from trie import (
    BinaryTrie,
    HexaryTrie,
)

from eth_utils import (
    keccak,
)
from evm.utils.numeric import (
    big_endian_to_int,
)
from evm.utils.state_access_restriction import (
    get_balance_key,
    get_storage_key,
)
from evm.constants import (
    BLANK_ROOT_HASH,
    EMPTY_SHA3,
    ZERO_HASH32,
)

from evm.db import (
    get_db_backend,
)
from evm.db.chain import (
    ChainDB,
)
from evm.db.state import (
    MainAccountStateDB,
    ShardingAccountStateDB,
)
from evm.exceptions import (
    BlockNotFound,
    ParentNotFound,
)
from evm.rlp.headers import (
    BlockHeader,
    CollationHeader,
)
from evm.tools.fixture_tests import (
    assert_rlp_equal,
)
from evm.utils.db import (
    get_empty_root_hash,
    make_block_hash_to_score_lookup_key,
    make_block_number_to_hash_lookup_key,
)
from evm.vm.forks.frontier.blocks import (
    FrontierBlock,
)
from evm.vm.forks.homestead.blocks import (
    HomesteadBlock,
)


A_ADDRESS = b"\xaa" * 20
B_ADDRESS = b"\xbb" * 20


def set_empty_root(chaindb, header):
    root_hash = get_empty_root_hash(chaindb)
    header.transaction_root = root_hash
    header.receipt_root = root_hash
    header.state_root = root_hash


@pytest.fixture(params=[MainAccountStateDB, ShardingAccountStateDB])
def chaindb(request):
    if request.param is MainAccountStateDB:
        trie_class = HexaryTrie
    else:
        trie_class = BinaryTrie
    return ChainDB(
        get_db_backend(),
        account_state_class=request.param,
        trie_class=trie_class,
    )


@pytest.fixture
def shard_chaindb(request):
    return ChainDB(
        get_db_backend(),
        account_state_class=ShardingAccountStateDB,
        trie_class=BinaryTrie,
    )


@pytest.fixture
def populated_shard_chaindb_and_root_hash(shard_chaindb):
    if shard_chaindb.trie_class is HexaryTrie:
        root_hash = BLANK_ROOT_HASH
    else:
        root_hash = EMPTY_SHA3

    state_db = shard_chaindb.get_state_db(root_hash, read_only=False)
    state_db.set_balance(A_ADDRESS, 1)
    state_db.set_code(B_ADDRESS, b"code")
    state_db.set_storage(B_ADDRESS, big_endian_to_int(b"key1"), 100)
    state_db.set_storage(B_ADDRESS, big_endian_to_int(b"key2"), 200)
    state_db.set_storage(B_ADDRESS, big_endian_to_int(b"key"), 300)
    return shard_chaindb, state_db.root_hash


@pytest.fixture(params=[0, 10, 999])
def header(request):
    block_number = request.param
    difficulty = 1
    gas_limit = 1
    return BlockHeader(difficulty, block_number, gas_limit)


@pytest.fixture(params=[FrontierBlock, HomesteadBlock])
def block(request, header):
    return request.param(header)


def test_add_block_number_to_hash_lookup(chaindb, block):
    block_number_to_hash_key = make_block_number_to_hash_lookup_key(block.number)
    assert not chaindb.exists(block_number_to_hash_key)
    chaindb._add_block_number_to_hash_lookup(block.header)
    assert chaindb.exists(block_number_to_hash_key)


def test_persist_header_to_db(chaindb, header):
    with pytest.raises(BlockNotFound):
        chaindb.get_block_header_by_hash(header.hash)
    number_to_hash_key = make_block_hash_to_score_lookup_key(header.hash)
    assert not chaindb.exists(number_to_hash_key)

    chaindb.persist_header_to_db(header)

    assert chaindb.get_block_header_by_hash(header.hash) == header
    assert chaindb.exists(number_to_hash_key)


@given(seed=st.binary(min_size=32, max_size=32))
def test_persist_header_to_db_unknown_parent(chaindb, header, seed):
    header.parent_hash = keccak(seed)
    with pytest.raises(ParentNotFound):
        chaindb.persist_header_to_db(header)


def test_persist_block_to_db(chaindb, block):
    set_empty_root(chaindb, block.header)
    block_to_hash_key = make_block_hash_to_score_lookup_key(block.hash)
    assert not chaindb.exists(block_to_hash_key)
    chaindb.persist_block_to_db(block)
    assert chaindb.exists(block_to_hash_key)


def test_get_score(chaindb):
    genesis = BlockHeader(difficulty=1, block_number=0, gas_limit=0)
    chaindb.persist_header_to_db(genesis)

    genesis_score_key = make_block_hash_to_score_lookup_key(genesis.hash)
    genesis_score = rlp.decode(chaindb.db.get(genesis_score_key), sedes=rlp.sedes.big_endian_int)
    assert genesis_score == 1
    assert chaindb.get_score(genesis.hash) == 1

    block1 = BlockHeader(difficulty=10, block_number=1, gas_limit=0, parent_hash=genesis.hash)
    chaindb.persist_header_to_db(block1)

    block1_score_key = make_block_hash_to_score_lookup_key(block1.hash)
    block1_score = rlp.decode(chaindb.db.get(block1_score_key), sedes=rlp.sedes.big_endian_int)
    assert block1_score == 11
    assert chaindb.get_score(block1.hash) == 11


def test_get_block_header_by_hash(chaindb, block, header):
    set_empty_root(chaindb, block.header)
    set_empty_root(chaindb, header)
    chaindb.persist_block_to_db(block)
    block_header = chaindb.get_block_header_by_hash(block.hash)
    assert_rlp_equal(block_header, header)


def test_lookup_block_hash(chaindb, block):
    set_empty_root(chaindb, block.header)
    chaindb._add_block_number_to_hash_lookup(block.header)
    block_hash = chaindb.lookup_block_hash(block.number)
    assert block_hash == block.hash


def test_get_witness_nodes(populated_shard_chaindb_and_root_hash):
    chaindb, root_hash = populated_shard_chaindb_and_root_hash
    header = CollationHeader(
        shard_id=1,
        expected_period_number=0,
        period_start_prevhash=ZERO_HASH32,
        parent_hash=ZERO_HASH32,
        number=0,
        state_root=root_hash
    )

    prefixes = [
        get_balance_key(A_ADDRESS),
        get_balance_key(B_ADDRESS),
        get_storage_key(A_ADDRESS, big_endian_to_int(b"key1")),
        get_storage_key(B_ADDRESS, big_endian_to_int(b"key1")),
        get_storage_key(B_ADDRESS, big_endian_to_int(b"key2")),
        get_storage_key(B_ADDRESS, big_endian_to_int(b"key")),
        get_storage_key(B_ADDRESS, big_endian_to_int(b"")),
    ]

    witness_nodes = chaindb.get_witness_nodes(header, prefixes)
    assert len(witness_nodes) == len(set(witness_nodes))  # no duplicates
    assert sorted(witness_nodes) == sorted(witness_nodes)  # sorted
