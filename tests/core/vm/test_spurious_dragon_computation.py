import pytest

from eth_utils import (
    to_canonical_address,
)

from eth.vm.message import (
    Message,
)

from eth.vm.forks.spurious_dragon.computation import (
    SpuriousDragonComputation,
)

from eth.vm.transaction_context import (
    BaseTransactionContext,
)


NORMALIZED_ADDRESS_A = "0x0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6"
NORMALIZED_ADDRESS_B = "0xcd1722f3947def4cf144679da39c4c32bdc35681"
CANONICAL_ADDRESS_A = to_canonical_address("0x0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6")
CANONICAL_ADDRESS_B = to_canonical_address("0xcd1722f3947def4cf144679da39c4c32bdc35681")
CONTRACT_CODE_A = b""
CONTRACT_CODE_B = b""
CONTRACT_CODE_C = b""


@pytest.fixture
def state(chain_without_block_validation):
    state = chain_without_block_validation.get_vm().state
    state.account_db.set_balance(CANONICAL_ADDRESS_A, 1000)
    return state


@pytest.fixture
def transaction_context():
    tx_context = BaseTransactionContext(
        gas_price=1,
        origin=CANONICAL_ADDRESS_B,
    )
    return tx_context


def test_code_size_limit(transaction_context, state):
    """
    CONTRACT_CODE_A size is greater than EIP170_CODE_SIZE_LIMIT
    """
    message_contract_code_a = Message(
        to=CANONICAL_ADDRESS_A,
        sender=CANONICAL_ADDRESS_B,
        value=100,
        data=b'',
        code=CONTRACT_CODE_A,
        gas=100,
    )
    computation = SpuriousDragonComputation(
        state=state,
        message=message_contract_code_a,
        transaction_context=transaction_context,
    )

    """
    TODO: CONTRACT_CODE_B size is equal to EIP170_CODE_SIZE_LIMIT
    """
    message_contract_code_b = Message(
        to=CANONICAL_ADDRESS_A,
        sender=CANONICAL_ADDRESS_B,
        value=100,
        data=b'',
        code=CONTRACT_CODE_B,
        gas=100,
    )

    """
    TODO: CONTRACT_CODE_C size is lower than EIP170_CODE_SIZE_LIMIT
    """
    message_contract_code_c = Message(
        to=CANONICAL_ADDRESS_A,
        sender=CANONICAL_ADDRESS_B,
        value=100,
        data=b'',
        code=CONTRACT_CODE_C,
        gas=100,
    )
