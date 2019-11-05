import pytest

from hypothesis import (
    given,
    strategies as st,
)

import rlp

from eth_hash.auto import keccak

from eth.constants import (
    BLANK_ROOT_HASH,
)
from eth.chains.base import (
    MiningChain,
)
from eth.db.chain import (
    ChainDB,
)
from eth.db.schema import SchemaV1
from eth.exceptions import (
    HeaderNotFound,
    ParentNotFound,
    ReceiptNotFound,
)
from eth.rlp.headers import (
    BlockHeader,
)
from eth.tools.rlp import (
    assert_headers_eq,
)
from eth._utils.address import (
    force_bytes_to_address,
)
from eth.vm.forks.frontier.blocks import (
    FrontierBlock,
)
from eth.vm.forks.homestead.blocks import (
    HomesteadBlock,
)
from eth.tools.factories.transaction import (
    new_transaction
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
def chaindb(base_db):
    return ChainDB(base_db)


@pytest.fixture(params=[0, 10, 999])
def header(request):
    block_number = request.param
    difficulty = 1
    gas_limit = 1
    return BlockHeader(difficulty, block_number, gas_limit)


@pytest.fixture(params=[FrontierBlock, HomesteadBlock])
def block(request, header):
    return request.param(header)


@pytest.fixture
def chain(chain_without_block_validation):
    if not isinstance(chain_without_block_validation, MiningChain):
        pytest.skip("these tests require a mining chain implementation")
    else:
        return chain_without_block_validation


def test_chaindb_add_block_number_to_hash_lookup(chaindb, block):
    block_number_to_hash_key = SchemaV1.make_block_number_to_hash_lookup_key(block.number)
    assert not chaindb.exists(block_number_to_hash_key)
    chaindb.persist_block(block)
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
    assert_headers_eq(block_header, header)


def test_chaindb_get_canonical_block_hash(chaindb, block):
    block = block.copy(header=set_empty_root(chaindb, block.header))
    chaindb.persist_block(block)
    block_hash = chaindb.get_canonical_block_hash(block.number)
    assert block_hash == block.hash


def test_chaindb_get_receipt_by_index(
        chain,
        funded_address,
        funded_address_private_key):
    NUMBER_BLOCKS_IN_CHAIN = 5
    TRANSACTIONS_IN_BLOCK = 10
    REQUIRED_BLOCK_NUMBER = 2
    REQUIRED_RECEIPT_INDEX = 3

    for block_number in range(NUMBER_BLOCKS_IN_CHAIN):
        for tx_index in range(TRANSACTIONS_IN_BLOCK):
            tx = new_transaction(
                chain.get_vm(),
                from_=funded_address,
                to=force_bytes_to_address(b'\x10\x10'),
                private_key=funded_address_private_key,
            )
            new_block, tx_receipt, computation = chain.apply_transaction(tx)
            computation.raise_if_error()

            if (block_number + 1) == REQUIRED_BLOCK_NUMBER and tx_index == REQUIRED_RECEIPT_INDEX:
                actual_receipt = tx_receipt

        chain.mine_block()

    # Check that the receipt retrieved is indeed the actual one
    chaindb_retrieved_receipt = chain.chaindb.get_receipt_by_index(
        REQUIRED_BLOCK_NUMBER,
        REQUIRED_RECEIPT_INDEX,
    )
    assert chaindb_retrieved_receipt == actual_receipt

    # Raise error if block number is not found
    with pytest.raises(ReceiptNotFound):
        chain.chaindb.get_receipt_by_index(
            NUMBER_BLOCKS_IN_CHAIN + 1,
            REQUIRED_RECEIPT_INDEX,
        )

    # Raise error if receipt index is out of range
    with pytest.raises(ReceiptNotFound):
        chain.chaindb.get_receipt_by_index(
            NUMBER_BLOCKS_IN_CHAIN,
            TRANSACTIONS_IN_BLOCK + 1,
        )
