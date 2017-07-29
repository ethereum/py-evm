import pytest

import rlp

from evm.utils.fixture_tests import (
    assert_rlp_equal,
)

from evm.utils.blocks import (
    add_block_number_to_hash_lookup,
    get_score,
    persist_block_to_db,
    get_block_header_by_hash,
    lookup_block_hash,
)

from evm.db import (
    get_db_backend,
)

from evm.vm.flavors.frontier.blocks import (
    FrontierBlock,
)

from evm.rlp.headers import (
    BlockHeader,
)

from evm.utils.db import (
    make_block_hash_to_score_lookup_key,
    make_block_number_to_hash_lookup_key,
)


@pytest.fixture
def db():
    return get_db_backend()


@pytest.fixture
def header():
    return BlockHeader(1, 1, 1)


@pytest.fixture
def block(header, db):
    return FrontierBlock(header, db)


def test_add_block_number_to_hash_lookup(db, block):
    block_number_to_hash_key = make_block_number_to_hash_lookup_key(1)
    assert not db.exists(block_number_to_hash_key)
    add_block_number_to_hash_lookup(db, block)
    assert db.exists(block_number_to_hash_key)


def test_perist_block_to_db(db, block):
    block_to_hash_key = make_block_hash_to_score_lookup_key(block.hash)
    assert not db.exists(block_to_hash_key)
    persist_block_to_db(db, block)
    assert db.exists(block_to_hash_key)


def test_get_score(db, block):
    persist_block_to_db(db, block)
    block_to_hash_key = make_block_hash_to_score_lookup_key(block.hash)
    score = rlp.decode(db.get(block_to_hash_key), sedes=rlp.sedes.big_endian_int)
    assert get_score(db, block.hash) == score


def test_get_block_header_by_hash(db, block, header):
    persist_block_to_db(db, block)
    block_header = get_block_header_by_hash(db, block.hash)
    assert_rlp_equal(block_header, header)


def test_lookup_block_hash(db, block):
    add_block_number_to_hash_lookup(db, block)
    block_hash = lookup_block_hash(db, 1)
    assert block_hash == block.hash
