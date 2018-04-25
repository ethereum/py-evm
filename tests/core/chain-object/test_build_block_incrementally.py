import pytest

from evm.utils.address import force_bytes_to_address

from tests.core.helpers import (
    new_transaction,
)


ADDRESS_1010 = force_bytes_to_address(b'\x10\x10')


@pytest.fixture
def chain(chain_without_block_validation):
    return chain_without_block_validation


def test_building_block_incrementally_with_single_transaction(chain,
                                                              funded_address,
                                                              funded_address_private_key):
    tx = new_transaction(
        chain.get_vm(),
        from_=funded_address,
        to=ADDRESS_1010,
        private_key=funded_address_private_key,
    )
    _, _, computation = chain.apply_transaction(tx)
    assert computation.is_success

    mined_block = chain.mine_block()
    assert len(mined_block.transactions) == 1

    actual_tx = mined_block.transactions[0]
    assert actual_tx == tx


def test_building_block_incrementally_with_multiple_transactions(chain,
                                                                 funded_address,
                                                                 funded_address_private_key):
    txns = []
    for _ in range(3):
        tx = new_transaction(
            chain.get_vm(),
            from_=funded_address,
            to=ADDRESS_1010,
            private_key=funded_address_private_key,
        )
        txns.append(tx)
        _, _, computation = chain.apply_transaction(tx)
        assert computation.is_success

    mined_block = chain.mine_block()
    assert len(mined_block.transactions) == 3

    for left, right in zip(txns, mined_block.transactions):
        assert left == right
