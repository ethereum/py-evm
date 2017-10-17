import pytest

import rlp

from evm.utils.fixture_tests import (
    assert_rlp_equal,
)

from evm.db import (
    get_db_backend,
)
from evm.db.chain import (
    BaseChainDB,
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


@pytest.fixture
def chaindb():
    return BaseChainDB(get_db_backend())


@pytest.fixture(params=[0, 10, 999])
def header(request):
    block_number = request.param
    difficulty = 1
    gas_limit = 1
    return BlockHeader(difficulty, block_number, gas_limit)


@pytest.fixture(params=[FrontierBlock, HomesteadBlock])
def block(request, header, chaindb):
    return request.param(header, chaindb)


def test_add_block_number_to_hash_lookup(chaindb, block):
    block_number_to_hash_key = make_block_number_to_hash_lookup_key(block.number)
    assert not chaindb.exists(block_number_to_hash_key)
    chaindb.add_block_number_to_hash_lookup(block)
    assert chaindb.exists(block_number_to_hash_key)


def test_persist_block_to_db(chaindb, block):
    block_to_hash_key = make_block_hash_to_score_lookup_key(block.hash)
    assert not chaindb.exists(block_to_hash_key)
    chaindb.persist_block_to_db(block)
    assert chaindb.exists(block_to_hash_key)


def test_get_score(chaindb, block):
    chaindb.persist_block_to_db(block)
    block_to_hash_key = make_block_hash_to_score_lookup_key(block.hash)
    score = rlp.decode(chaindb.db.get(block_to_hash_key), sedes=rlp.sedes.big_endian_int)
    assert chaindb.get_score(block.hash) == score


def test_get_block_header_by_hash(chaindb, block, header):
    chaindb.persist_block_to_db(block)
    block_header = chaindb.get_block_header_by_hash(block.hash)
    assert_rlp_equal(block_header, header)


def test_lookup_block_hash(chaindb, block):
    chaindb.add_block_number_to_hash_lookup(block)
    block_hash = chaindb.lookup_block_hash(block.number)
    assert block_hash == block.hash
