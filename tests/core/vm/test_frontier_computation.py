import pytest

from eth.vm.message import (
    Message,
)
from eth.vm.forks.frontier.computation import (
    FrontierComputation,
)
from tests.core.vm.conftest import CANONICAL_ADDRESS_A, CANONICAL_ADDRESS_B


@pytest.fixture
def state(chain_without_block_validation):
    state = chain_without_block_validation.get_vm().state
    state.set_balance(CANONICAL_ADDRESS_A, 1000)
    return state


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
        state=state,
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
    child_computation = computation.generate_child_computation(child_message)
    return child_computation


def test_generate_child_computation(computation, child_computation):
    assert computation.transaction_context.gas_price == child_computation.transaction_context.gas_price  # noqa: E501
    assert computation.transaction_context.origin == child_computation.transaction_context.origin  # noqa: E501
