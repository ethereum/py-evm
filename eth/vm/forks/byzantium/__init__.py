from typing import (  # noqa: F401
    Type,
)

from cytoolz import (
    curry,
)

from eth_utils import (
    encode_hex,
    ValidationError,
)

from eth.constants import (
    MAX_UNCLE_DEPTH,
)
from eth.rlp.blocks import BaseBlock  # noqa: F401
from eth.rlp.receipts import Receipt
from eth.validation import (
    validate_lte,
)
from eth.vm.forks.spurious_dragon import SpuriousDragonVM
from eth.vm.forks.frontier import make_frontier_receipt
from eth.vm.state import BaseState  # noqa: F401

from .blocks import ByzantiumBlock
from .constants import (
    EIP649_BLOCK_REWARD,
    EIP658_TRANSACTION_STATUS_CODE_FAILURE,
    EIP658_TRANSACTION_STATUS_CODE_SUCCESS,
)
from .headers import (
    create_byzantium_header_from_parent,
    configure_byzantium_header,
    compute_byzantium_difficulty,
)
from .state import ByzantiumState


def make_byzantium_receipt(base_header, transaction, computation, state):
    frontier_receipt = make_frontier_receipt(base_header, transaction, computation, state)

    if computation.is_error:
        status_code = EIP658_TRANSACTION_STATUS_CODE_FAILURE
    else:
        status_code = EIP658_TRANSACTION_STATUS_CODE_SUCCESS

    return frontier_receipt.copy(state_root=status_code)


@curry
def get_uncle_reward(block_reward, block_number, uncle):
    block_number_delta = block_number - uncle.block_number
    validate_lte(block_number_delta, MAX_UNCLE_DEPTH)
    return (8 - block_number_delta) * block_reward // 8


EIP658_STATUS_CODES = {
    EIP658_TRANSACTION_STATUS_CODE_SUCCESS,
    EIP658_TRANSACTION_STATUS_CODE_FAILURE,
}


class ByzantiumVM(SpuriousDragonVM):
    # fork name
    fork = 'byzantium'

    # classes
    block_class = ByzantiumBlock  # type: Type[BaseBlock]
    _state_class = ByzantiumState  # type: Type[BaseState]

    # Methods
    create_header_from_parent = staticmethod(create_byzantium_header_from_parent)
    compute_difficulty = staticmethod(compute_byzantium_difficulty)
    configure_header = configure_byzantium_header
    make_receipt = staticmethod(make_byzantium_receipt)
    get_uncle_reward = staticmethod(get_uncle_reward(EIP649_BLOCK_REWARD))

    @classmethod
    def validate_receipt(cls, receipt: Receipt) -> None:
        super().validate_receipt(receipt)
        if receipt.state_root not in EIP658_STATUS_CODES:
            raise ValidationError(
                "The receipt's `state_root` must be one of [{0}, {1}].  Got: "
                "{2}".format(
                    encode_hex(EIP658_TRANSACTION_STATUS_CODE_SUCCESS),
                    encode_hex(EIP658_TRANSACTION_STATUS_CODE_FAILURE),
                    encode_hex(receipt.state_root),
                )
            )

    @staticmethod
    def get_block_reward():
        return EIP649_BLOCK_REWARD
