import pytest

from eth._utils.address import (
    force_bytes_to_address,
)
from eth.chains.base import (
    MiningChain,
)
from eth.tools.factories.transaction import (
    new_transaction,
)

ADDRESS_1010 = force_bytes_to_address(b"\x10\x10")


@pytest.fixture
def chain(chain_without_block_validation):
    if not isinstance(chain_without_block_validation, MiningChain):
        pytest.skip("these tests require a mining chain implementation")
    else:
        return chain_without_block_validation


def test_building_block_incrementally_with_single_transaction(
    chain, funded_address, funded_address_private_key
):
    head_hash = chain.get_canonical_head().hash
    tx = new_transaction(
        chain.get_vm(),
        from_=funded_address,
        to=ADDRESS_1010,
        private_key=funded_address_private_key,
    )
    _, _, computation = chain.apply_transaction(tx)
    computation.raise_if_error()

    # test that the *latest* block hasn't changed
    assert chain.get_canonical_head().hash == head_hash

    mined_block = chain.mine_block()
    assert len(mined_block.transactions) == 1

    actual_tx = mined_block.transactions[0]
    assert actual_tx == tx


def test_building_block_incrementally_with_multiple_transactions(
    chain, funded_address, funded_address_private_key
):
    txns = []
    head_hash = chain.get_canonical_head().hash
    for expected_len in range(1, 4):
        tx = new_transaction(
            chain.get_vm(),
            from_=funded_address,
            to=ADDRESS_1010,
            private_key=funded_address_private_key,
        )
        txns.append(tx)
        _, _, computation = chain.apply_transaction(tx)
        computation.raise_if_error()

        # test that the pending block has the expected number of transactions
        vm = chain.get_vm()
        assert len(vm.get_block().transactions) == expected_len
        assert vm.get_block().transactions[-1] == tx

        # test that the *latest* block hasn't changed
        assert chain.get_canonical_head().hash == head_hash

    mined_block = chain.mine_block()
    assert len(mined_block.transactions) == 3

    for expected, actual in zip(txns, mined_block.transactions):
        assert expected == actual
