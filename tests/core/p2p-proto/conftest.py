import pytest

from eth.db.atomic import AtomicDB

from tests.core.integration_test_helpers import (
    load_fixture_db,
    load_mining_chain,
    DBFixture,
)


@pytest.fixture
def leveldb_20():
    yield from load_fixture_db(DBFixture.TWENTY_POW_HEADERS)


@pytest.fixture
def leveldb_1000():
    yield from load_fixture_db(DBFixture.THOUSAND_POW_HEADERS)


@pytest.fixture
def chaindb_1000(leveldb_1000):
    chain = load_mining_chain(AtomicDB(leveldb_1000))
    assert chain.chaindb.get_canonical_head().block_number == 1000
    return chain.chaindb


@pytest.fixture
def chaindb_20(leveldb_20):
    chain = load_mining_chain(AtomicDB(leveldb_20))
    assert chain.chaindb.get_canonical_head().block_number == 20
    return chain.chaindb


@pytest.fixture
def chaindb_fresh():
    chain = load_mining_chain(AtomicDB())
    assert chain.chaindb.get_canonical_head().block_number == 0
    return chain.chaindb
