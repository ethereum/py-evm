import random

import pytest

from eth_utils import (
    to_tuple,
    keccak,
)

from eth.db.header import HeaderDB
from eth.chains.header import HeaderChain

from eth.constants import (
    GENESIS_BLOCK_NUMBER,
    GENESIS_DIFFICULTY,
    GENESIS_GAS_LIMIT,
)
from eth.rlp.headers import (
    BlockHeader,
)
from eth.tools.rlp import (
    assert_headers_eq,
)


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


def test_header_chain_get_canonical_block_hash_passthrough(header_chain, genesis_header):
    assert header_chain.get_canonical_block_hash(0) == genesis_header.hash


def test_header_chain_get_canonical_block_header_by_number_passthrough(
        header_chain,
        genesis_header):
    assert header_chain.get_canonical_block_header_by_number(0) == genesis_header


def test_header_chain_get_canonical_head_passthrough(header_chain):
    assert header_chain.get_canonical_head() == header_chain.header


def test_header_chain_import_block(header_chain, genesis_header):
    chain_a = mk_header_chain(genesis_header, 3)
    chain_b = mk_header_chain(genesis_header, 2)
    chain_c = mk_header_chain(genesis_header, 5)

    for header in chain_a:
        res, _ = header_chain.import_header(header)
        assert res == (header,)
        assert_headers_eq(header_chain.header, header)

    for header in chain_b:
        res, _ = header_chain.import_header(header)
        assert res == ()
        assert_headers_eq(header_chain.header, chain_a[-1])

    for idx, header in enumerate(chain_c, 1):
        res, _ = header_chain.import_header(header)
        if idx <= 3:
            # prior to passing up `chain_a` each import should not return new
            # canonical headers.
            assert res == ()
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


def test_header_chain_get_block_header_by_hash_passthrough(header_chain, genesis_header):
    assert header_chain.get_block_header_by_hash(genesis_header.hash) == genesis_header


def test_header_chain_header_exists(header_chain, genesis_header):
    assert header_chain.header_exists(genesis_header.hash) is True
    assert header_chain.header_exists(b'\x0f' * 32) is False
