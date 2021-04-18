import json
import os
import pytest

from eth_utils import (
    to_canonical_address,
    decode_hex,
)

from eth.vm.message import (
    Message,
)
from eth.vm.forks.spurious_dragon.computation import (
    SpuriousDragonComputation,
)
from eth.vm.forks.spurious_dragon.constants import (
    EIP170_CODE_SIZE_LIMIT,
)
from eth.vm.transaction_context import (
    BaseTransactionContext,
)

CANONICAL_ADDRESS_A = to_canonical_address("0x0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6")
CANONICAL_ADDRESS_B = to_canonical_address("0xcd1722f3947def4cf144679da39c4c32bdc35681")


def contract_code_json():
    filepath = os.path.join(os.path.dirname(__file__),
                            'fixtures/spurious_dragon_computation_test_code_size_limitation.json')
    with open(filepath) as f:
        return json.load(f)


@pytest.fixture
def state(chain_with_block_validation):
    state = chain_with_block_validation.get_vm().state
    state.set_balance(CANONICAL_ADDRESS_A, 1000)
    return state


@pytest.fixture
def transaction_context():
    tx_context = BaseTransactionContext(
        gas_price=0,
        origin=CANONICAL_ADDRESS_A,
    )
    return tx_context


def _create_message(code):
    message = Message(
        to=CANONICAL_ADDRESS_B,
        sender=CANONICAL_ADDRESS_A,
        value=0,
        data=b'',
        code=code,
        gas=5000000,
    )
    return message


@pytest.mark.parametrize(
    'message, code_size, is_error',
    (
        (
            # CODE_SIZE == 24575
            _create_message(decode_hex(contract_code_json()['code_1'])),
            EIP170_CODE_SIZE_LIMIT - 1,
            False,
        ),
        (
            # CODE_SIZE == 24576
            _create_message(decode_hex(contract_code_json()['code_2'])),
            0,
            True,
        ),
        (
            # CODE_SIZE == 24577
            _create_message(decode_hex(contract_code_json()['code_3'])),
            0,
            True,
        )
    )
)
def test_code_size_limit_eip_170(state, message, transaction_context, code_size, is_error):
    computation = SpuriousDragonComputation(
        state=state,
        message=message,
        transaction_context=transaction_context,
    ).apply_create_message(state, message, transaction_context)

    assert len(computation.output) == code_size
    assert computation.is_error == is_error
