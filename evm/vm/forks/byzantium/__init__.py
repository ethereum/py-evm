from evm.rlp.receipts import (
    Receipt,
)
from evm.vm.forks.spurious_dragon import SpuriousDragonVM
from evm.vm.forks.frontier import make_frontier_receipt

from .constants import (
    EIP658_TRANSACTION_STATUS_CODE_FAILURE,
    EIP658_TRANSACTION_STATUS_CODE_SUCCESS,
)
from .headers import (
    create_byzantium_header_from_parent,
    configure_byzantium_header,
    compute_byzantium_difficulty,
)
from .state import ByzantiumState


def make_byzantium_receipt(transaction, computation, state):
    old_receipt = make_frontier_receipt(transaction, computation, state)

    if computation.is_error:
        state_root = EIP658_TRANSACTION_STATUS_CODE_FAILURE
    else:
        state_root = EIP658_TRANSACTION_STATUS_CODE_SUCCESS

    receipt = Receipt(
        state_root=state_root,
        gas_used=old_receipt.gas_used,
        logs=old_receipt.logs,
    )
    return receipt


ByzantiumVM = SpuriousDragonVM.configure(
    # class name
    __name__='ByzantiumVM',
    # fork name
    fork='byzantium',
    # classes
    _state_class=ByzantiumState,
    # Methods
    create_header_from_parent=staticmethod(create_byzantium_header_from_parent),
    compute_difficulty=staticmethod(compute_byzantium_difficulty),
    configure_header=configure_byzantium_header,
    make_receipt=staticmethod(make_byzantium_receipt)
)
