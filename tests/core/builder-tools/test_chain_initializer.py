import time

from eth_utils.toolz import (
    pipe,
)
import pytest

from eth import (
    constants,
)
from eth.chains.base import (
    Chain,
)
from eth.tools.builder.chain import (
    frontier_at,
    genesis,
)


@pytest.fixture
def chain_class():
    return frontier_at(0)(Chain)


def test_chain_builder_initialize_chain_default(chain_class):
    chain = pipe(
        chain_class,
        genesis(),
    )

    header = chain.get_canonical_head()
    assert header == chain.get_canonical_block_by_number(0).header

    assert header.parent_hash == constants.GENESIS_PARENT_HASH
    assert header.uncles_hash == constants.EMPTY_UNCLE_HASH
    assert header.coinbase == constants.GENESIS_COINBASE
    assert header.state_root == constants.BLANK_ROOT_HASH
    assert header.transaction_root == constants.BLANK_ROOT_HASH
    assert header.receipt_root == constants.BLANK_ROOT_HASH
    assert header.bloom == 0
    assert header.difficulty == 1
    assert header.block_number == constants.GENESIS_BLOCK_NUMBER
    assert header.gas_limit == constants.GENESIS_GAS_LIMIT
    assert header.gas_used == 0
    # account for runtime.  should run in less than few seconds and should be
    # effectively "now"
    assert abs(header.timestamp - time.time()) < 2
    assert header.extra_data == constants.GENESIS_EXTRA_DATA
    assert header.mix_hash == constants.GENESIS_MIX_HASH
    assert header.nonce == constants.GENESIS_NONCE


ADDRESS_A = b"a" + b"\0" * 19
ADDRESS_B = b"b" + b"\0" * 19


def test_chain_builder_initialize_chain_with_state_simple(chain_class):
    chain = pipe(
        chain_class,
        genesis(
            state=((ADDRESS_A, "balance", 1),),
        ),
    )

    header = chain.get_canonical_head()
    assert header == chain.get_canonical_block_by_number(0).header

    assert header.state_root != constants.BLANK_ROOT_HASH

    state = chain.get_vm().state
    assert state.get_balance(ADDRESS_A) == 1


def test_chain_builder_initialize_chain_with_state_multiple(chain_class):
    chain = pipe(
        chain_class,
        genesis(
            state=((ADDRESS_A, "balance", 1), (ADDRESS_B, "balance", 2)),
        ),
    )

    header = chain.get_canonical_head()
    assert header == chain.get_canonical_block_by_number(0).header

    assert header.state_root != constants.BLANK_ROOT_HASH

    state = chain.get_vm().state
    assert state.get_balance(ADDRESS_A) == 1
    assert state.get_balance(ADDRESS_B) == 2


def test_chain_builder_initialize_chain_with_params(chain_class):
    chain = pipe(
        chain_class,
        genesis(
            params={"difficulty": 12345},
        ),
    )

    header = chain.get_canonical_head()
    assert header == chain.get_canonical_block_by_number(0).header

    assert header.difficulty == 12345


def test_chain_builder_initialize_chain_with_params_and_state(chain_class):
    chain = pipe(
        chain_class,
        genesis(
            params={"difficulty": 12345},
            state=((ADDRESS_A, "balance", 1),),
        ),
    )

    header = chain.get_canonical_head()
    assert header == chain.get_canonical_block_by_number(0).header

    assert header.difficulty == 12345

    assert header.state_root != constants.BLANK_ROOT_HASH

    state = chain.get_vm().state
    assert state.get_balance(ADDRESS_A) == 1
