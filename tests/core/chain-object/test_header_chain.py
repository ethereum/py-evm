import random

import pytest

from eth_utils import (
    to_tuple,
    keccak,
)

from evm.db.header import HeaderDB
from evm.chains.header import HeaderChain

from evm.constants import (
    GENESIS_BLOCK_NUMBER,
    GENESIS_DIFFICULTY,
    GENESIS_GAS_LIMIT,
)
from evm.db.backends.memory import MemoryDB
from evm.rlp.headers import (
    BlockHeader,
)
from evm.utils.rlp import (
    ensure_rlp_objects_are_equal,
)


assert_headers_eq = ensure_rlp_objects_are_equal(obj_a_name='actual', obj_b_name='expected')


@to_tuple
def mk_header_chain(base_header, length):
    previous_header = base_header
    for _ in range(length):
        next_header = BlockHeader.from_parent(
            parent=previous_header,
            timestamp=previous_header.timestamp + 1,
            gas_limit=previous_header.gas_limit,
            difficulty=previous_header.difficulty,
            extra_data=keccak(random.randint(0, 1e18)),
        )
        yield next_header
        previous_header = next_header


@pytest.fixture
def base_db():
    return MemoryDB()


@pytest.fixture
def headerdb(base_db):
    return HeaderDB(base_db)


@pytest.fixture
def genesis_header():
    return BlockHeader(
        difficulty=GENESIS_DIFFICULTY,
        block_number=GENESIS_BLOCK_NUMBER,
        gas_limit=GENESIS_GAS_LIMIT,
    )


@pytest.fixture()
def header_chain(base_db, genesis_header):
    return HeaderChain.from_genesis_header(base_db, genesis_header)


def test_header_chain_initialization_from_genesis_header(base_db, genesis_header):
    header_chain = HeaderChain.from_genesis_header(base_db, genesis_header)

    head = header_chain.get_canonical_head()
    assert_headers_eq(head, genesis_header)


def test_header_chain_initialization_header_already_persisted(base_db, genesis_header):
    headerdb = HeaderDB(base_db)
    headerdb.persist_header(genesis_header)

    # sanity check that the header is persisted
    assert_headers_eq(headerdb.get_canonical_head(), genesis_header)

    header_chain = HeaderChain.from_genesis_header(base_db, genesis_header)

    head = header_chain.get_canonical_head()
    assert_headers_eq(head, genesis_header)


def test_header_chain_get_canonical_block_hash_passthrough(headerdb, header_chain):
    headers = mk_header_chain(headerdb.get_canonical_head(), 10)

    # push headers directly into database
    for header in headers:
        headerdb.persist_header(header)

    for header in headers:
        canonical_hash = header_chain.get_canonical_block_hash(header.block_number)
        assert canonical_hash == header.hash


def test_header_chain_get_canonical_block_header_by_number_passthrough(headerdb, header_chain):
    headers = mk_header_chain(headerdb.get_canonical_head(), 10)

    # push headers directly into database
    for header in headers:
        headerdb.persist_header(header)

    for header in headers:
        canonical_header = header_chain.get_canonical_block_header_by_number(header.block_number)
        assert_headers_eq(canonical_header, header)


def test_header_chain_get_canonical_head_passthrough(headerdb, header_chain, genesis_header):
    headers = mk_header_chain(genesis_header, 10)

    # push headers directly into database
    for header in headers:
        headerdb.persist_header(header)
        head = header_chain.get_canonical_head()
        assert_headers_eq(head, header)


def test_header_chain_import_block(header_chain, genesis_header):
    chain_a = mk_header_chain(genesis_header, 3)
    chain_b = mk_header_chain(genesis_header, 2)
    chain_c = mk_header_chain(genesis_header, 5)

    for header in chain_a:
        res = header_chain.import_header(header)
        assert res == (header,)
        assert_headers_eq(header_chain.header, header)

    for header in chain_b:
        res = header_chain.import_header(header)
        assert res == tuple()
        assert_headers_eq(header_chain.header, chain_a[-1])

    for idx, header in enumerate(chain_c, 1):
        res = header_chain.import_header(header)
        if idx <= 3:
            # prior to passing up `chain_a` each import should not return new
            # canonical headers.
            assert res == tuple()
            assert_headers_eq(header_chain.header, chain_a[-1])
        elif idx == 4:
            # at the point where `chain_c` passes `chain_a` we should get the
            # headers from `chain_c` up through current.
            assert res == chain_c[:idx]
            assert_headers_eq(res[-1], header)
            assert_headers_eq(header_chain.header, header)
        else:
            # after `chain_c` has become canonical we should just get each new
            # header back.
            assert res == (header,)
            assert_headers_eq(header_chain.header, header)

    assert_headers_eq(header_chain.header, chain_c[-1])


def test_header_chain_get_block_header_by_hash_passthrough(headerdb, header_chain):
    chain_a = mk_header_chain(headerdb.get_canonical_head(), 5)
    chain_b = mk_header_chain(headerdb.get_canonical_head(), 7)

    # push both chains of headers into the database
    for header in chain_a:
        headerdb.persist_header(header)
    for header in chain_b:
        headerdb.persist_header(header)

    # verify we can retrieve both `chain_a` and `chain_b` headers
    for header in chain_a:
        actual = header_chain.get_block_header_by_hash(header.hash)
        assert actual == header
    for header in chain_b:
        actual = header_chain.get_block_header_by_hash(header.hash)
        assert actual == header
