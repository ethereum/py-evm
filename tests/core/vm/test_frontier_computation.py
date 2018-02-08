import pytest

from evm.transaction_context import (
    BaseTransactionContext,
)
from evm.vm import (
    Message,
)
from evm.vm.forks.frontier.computation import (
    FrontierComputation,
)

from eth_utils import (
    to_canonical_address,
)

from tests.core.fixtures import chain_without_block_validation  # noqa: F401

NORMALIZED_ADDRESS_A = "0x0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6"
NORMALIZED_ADDRESS_B = "0xcd1722f3947def4cf144679da39c4c32bdc35681"
CANONICAL_ADDRESS_A = to_canonical_address("0x0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6")
CANONICAL_ADDRESS_B = to_canonical_address("0xcd1722f3947def4cf144679da39c4c32bdc35681")


@pytest.fixture  # noqa: F811
def state(chain_without_block_validation):
    state = chain_without_block_validation.get_vm().state
    with state.state_db() as state_db:
        state_db.set_balance(CANONICAL_ADDRESS_A, 1000)
    return state


@pytest.fixture
def transaction_context():
    tx_context = BaseTransactionContext(
        gas_price=1,
        origin=CANONICAL_ADDRESS_B,
    )
    return tx_context


@pytest.fixture
def message():
    message = Message(
        to=CANONICAL_ADDRESS_A,
        sender=CANONICAL_ADDRESS_B,
        value=100,
        data=b'',
        code=b'',
        gas=100,
    )
    return message


@pytest.fixture
def computation(message, transaction_context, state):
    computation = FrontierComputation(
        vm_state=state,
        message=message,
        transaction_context=transaction_context,
    )
    return computation


@pytest.fixture
def child_message(computation):
    child_message = computation.prepare_child_message(
        gas=100,
        to=CANONICAL_ADDRESS_B,
        value=200,
        data=b'',
        code=b''
    )
    return child_message


@pytest.fixture
def child_computation(computation, child_message):
    child_computation = computation.generate_child_computation(
        computation.vm_state,
        child_message,
        computation.transaction_context,
    )
    return child_computation


def test_generate_child_computation(computation, child_computation):
    assert computation.transaction_context.gas_price == child_computation.transaction_context.gas_price  # noqa: E501
    assert computation.transaction_context.origin == child_computation.transaction_context.origin  # noqa: E501
