import pytest

from hypothesis import (
    given,
    strategies as st,
)

import rlp

from evm.utils.fixture_tests import (
    assert_rlp_equal,
)

from evm.db import (
    get_db_backend,
)
from evm.db.chain import (
    ChainDB,
)
from evm.exceptions import (
    BlockNotFound,
    ParentNotFound,
)

from evm.vm.forks.frontier.blocks import (
    FrontierBlock,
)
from evm.vm.forks.homestead.blocks import (
    HomesteadBlock,
)

from evm.rlp.headers import (
    BlockHeader,
)

from evm.utils.db import (
    make_block_hash_to_score_lookup_key,
    make_block_number_to_hash_lookup_key,
)
from evm.utils.keccak import (
    keccak,
)


@pytest.fixture
def chaindb():
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
    chaindb.persist_block_to_db(block)
    block_header = chaindb.get_block_header_by_hash(block.hash)
    assert_rlp_equal(block_header, header)


def test_lookup_block_hash(chaindb, block):
    chaindb._add_block_number_to_hash_lookup(block.header)
    block_hash = chaindb.lookup_block_hash(block.number)
    assert block_hash == block.hash
