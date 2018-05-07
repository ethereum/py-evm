import pytest

from hypothesis import (
    given,
    strategies as st,
)

import rlp

from eth_hash.auto import keccak

from evm.constants import (
    BLANK_ROOT_HASH,
)
from evm.db import (
    get_db_backend,
)
from evm.db.chain import (
    ChainDB,
)
from evm.db.schema import SchemaV1
from evm.exceptions import (
    HeaderNotFound,
    ParentNotFound,
)
from evm.rlp.headers import (
    BlockHeader,
)
from evm.tools.fixture_tests import (
    assert_rlp_equal,
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
    return header.copy(
        transaction_root=BLANK_ROOT_HASH,
        receipt_root=BLANK_ROOT_HASH,
        state_root=BLANK_ROOT_HASH,
    )


@pytest.fixture
def chaindb(request):
    return ChainDB(get_db_backend())


@pytest.fixture(params=[0, 10, 999])
def header(request):
    block_number = request.param
    difficulty = 1
    gas_limit = 1
    return BlockHeader(difficulty, block_number, gas_limit)


@pytest.fixture(params=[FrontierBlock, HomesteadBlock])
def block(request, header):
    return request.param(header)


def test_chaindb_add_block_number_to_hash_lookup(chaindb, block):
    block_number_to_hash_key = SchemaV1.make_block_number_to_hash_lookup_key(block.number)
    assert not chaindb.exists(block_number_to_hash_key)
    chaindb._add_block_number_to_hash_lookup(block.header)
    assert chaindb.exists(block_number_to_hash_key)


def test_chaindb_persist_header(chaindb, header):
    with pytest.raises(HeaderNotFound):
        chaindb.get_block_header_by_hash(header.hash)
    number_to_hash_key = SchemaV1.make_block_hash_to_score_lookup_key(header.hash)
    assert not chaindb.exists(number_to_hash_key)

    chaindb.persist_header(header)

    assert chaindb.get_block_header_by_hash(header.hash) == header
    assert chaindb.exists(number_to_hash_key)


@given(seed=st.binary(min_size=32, max_size=32))
def test_chaindb_persist_header_unknown_parent(chaindb, header, seed):
    n_header = header.copy(parent_hash=keccak(seed))
    with pytest.raises(ParentNotFound):
        chaindb.persist_header(n_header)


def test_chaindb_persist_block(chaindb, block):
    block = block.copy(header=set_empty_root(chaindb, block.header))
    block_to_hash_key = SchemaV1.make_block_hash_to_score_lookup_key(block.hash)
    assert not chaindb.exists(block_to_hash_key)
    chaindb.persist_block(block)
    assert chaindb.exists(block_to_hash_key)


def test_chaindb_get_score(chaindb):
    genesis = BlockHeader(difficulty=1, block_number=0, gas_limit=0)
    chaindb.persist_header(genesis)

    genesis_score_key = SchemaV1.make_block_hash_to_score_lookup_key(genesis.hash)
    genesis_score = rlp.decode(chaindb.db.get(genesis_score_key), sedes=rlp.sedes.big_endian_int)
    assert genesis_score == 1
    assert chaindb.get_score(genesis.hash) == 1

    block1 = BlockHeader(difficulty=10, block_number=1, gas_limit=0, parent_hash=genesis.hash)
    chaindb.persist_header(block1)

    block1_score_key = SchemaV1.make_block_hash_to_score_lookup_key(block1.hash)
    block1_score = rlp.decode(chaindb.db.get(block1_score_key), sedes=rlp.sedes.big_endian_int)
    assert block1_score == 11
    assert chaindb.get_score(block1.hash) == 11


def test_chaindb_get_block_header_by_hash(chaindb, block, header):
    block = block.copy(header=set_empty_root(chaindb, block.header))
    header = set_empty_root(chaindb, header)
    chaindb.persist_block(block)
    block_header = chaindb.get_block_header_by_hash(block.hash)
    assert_rlp_equal(block_header, header)


def test_chaindb_get_canonical_block_hash(chaindb, block):
    block = block.copy(header=set_empty_root(chaindb, block.header))
    chaindb._add_block_number_to_hash_lookup(block.header)
    block_hash = chaindb.get_canonical_block_hash(block.number)
    assert block_hash == block.hash
