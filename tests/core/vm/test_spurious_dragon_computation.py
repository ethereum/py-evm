from unittest import mock

import pytest
from eth_utils import (
    to_canonical_address,
)

from eth import (
    Chain,
)
from eth.vm.computation import (
    BaseComputation,
)
from eth.vm.forks.spurious_dragon.computation import (
    SpuriousDragonComputation,
)
from eth.vm.forks.spurious_dragon.constants import (
    EIP170_CODE_SIZE_LIMIT
)
from eth.vm.message import (
    Message,
)
from eth.vm.transaction_context import (
    BaseTransactionContext,
)

NORMALIZED_ADDRESS_A = "0x0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6"
NORMALIZED_ADDRESS_B = "0xcd1722f3947def4cf144679da39c4c32bdc35681"
CANONICAL_ADDRESS_A = to_canonical_address(NORMALIZED_ADDRESS_A)
CANONICAL_ADDRESS_B = to_canonical_address(NORMALIZED_ADDRESS_B)


@pytest.fixture
def make_computation():
    message = Message(
        to=CANONICAL_ADDRESS_B,
        sender=CANONICAL_ADDRESS_A,
        value=1,
        data=b'',
        code=b'',
        gas=5000000,
    )
    transaction_context = BaseTransactionContext(gas_price=1, origin=CANONICAL_ADDRESS_B, )

    def _make_computation(chain) -> BaseComputation:
        state = chain.get_vm().state
        state.set_balance(CANONICAL_ADDRESS_A, 1000)
        computation = SpuriousDragonComputation(
            state=state,
            message=message,
            transaction_context=transaction_context,
        )

        return computation

    return _make_computation


@pytest.mark.parametrize('chain_without_block_validation', [Chain, ], indirect=True)
@pytest.mark.parametrize(
    'computation_output',
    [
        b'\x00' * (EIP170_CODE_SIZE_LIMIT + 1),
        b'\x00' * EIP170_CODE_SIZE_LIMIT,
        b'\x00' * (EIP170_CODE_SIZE_LIMIT - 1),
    ]
)
def test_computation_output_size_limit(chain_without_block_validation,
                                       make_computation,
                                       computation_output):
    computation: BaseComputation = make_computation(chain_without_block_validation)
    computation.output = computation_output

    with mock.patch.object(SpuriousDragonComputation, 'apply_message', return_value=computation):
        computation.apply_create_message()

        if len(computation_output) >= EIP170_CODE_SIZE_LIMIT:
            assert computation.is_error
        else:
            assert not computation.is_error
