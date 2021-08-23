import pytest
from eth_utils import to_canonical_address

from eth.vm.transaction_context import BaseTransactionContext


NORMALIZED_ADDRESS_A = "0x0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6"
NORMALIZED_ADDRESS_B = "0xcd1722f3947def4cf144679da39c4c32bdc35681"
CANONICAL_ADDRESS_A = to_canonical_address("0x0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6")
CANONICAL_ADDRESS_B = to_canonical_address("0xcd1722f3947def4cf144679da39c4c32bdc35681")


@pytest.fixture
def transaction_context():
    tx_context = BaseTransactionContext(
        gas_price=1,
        origin=CANONICAL_ADDRESS_B,
    )
    return tx_context

