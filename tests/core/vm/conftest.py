from eth_utils import (
    to_canonical_address,
)
import pytest

from eth.vm.transaction_context import (
    BaseTransactionContext,
)


@pytest.fixture
def normalized_address_a():
    return "0x0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6"


@pytest.fixture
def normalized_address_b():
    return "0xcd1722f3947def4cf144679da39c4c32bdc35681"


@pytest.fixture
def canonical_address_a(normalized_address_a):
    return to_canonical_address(normalized_address_a)


@pytest.fixture
def canonical_address_b(normalized_address_b):
    return to_canonical_address(normalized_address_b)


@pytest.fixture
def transaction_context(canonical_address_b):
    tx_context = BaseTransactionContext(
        gas_price=1,
        origin=canonical_address_b,
    )
    return tx_context
