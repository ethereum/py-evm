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


def make_byzantium_receipt(base_header, transaction, computation, state):
    frontier_receipt = make_frontier_receipt(base_header, transaction, computation, state)

    if computation.is_error:
        status_code = EIP658_TRANSACTION_STATUS_CODE_FAILURE
    else:
        status_code = EIP658_TRANSACTION_STATUS_CODE_SUCCESS

    return frontier_receipt.copy(state_root=status_code)


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
