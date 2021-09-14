from typing import (
    Type,
)

from eth.abc import (
    BlockHeaderAPI,
    ComputationAPI,
    ReceiptAPI,
    SignedTransactionAPI,
    StateAPI,
)
from eth.rlp.blocks import BaseBlock
from eth.vm.forks import (
    MuirGlacierVM,
)
from eth.vm.forks.byzantium.constants import (
    EIP658_TRANSACTION_STATUS_CODE_FAILURE,
    EIP658_TRANSACTION_STATUS_CODE_SUCCESS,
)
from eth.vm.state import BaseState

from .blocks import BerlinBlock
from .headers import (
    compute_berlin_difficulty,
    configure_berlin_header,
    create_berlin_header_from_parent,
)
from .state import BerlinState


class BerlinVM(MuirGlacierVM):
    # fork name
    fork = 'berlin'

    # classes
    block_class: Type[BaseBlock] = BerlinBlock
    _state_class: Type[BaseState] = BerlinState

    # Methods
    create_header_from_parent = staticmethod(create_berlin_header_from_parent)  # type: ignore
    compute_difficulty = staticmethod(compute_berlin_difficulty)    # type: ignore
    configure_header = configure_berlin_header

    @classmethod
    def make_receipt(
            cls,
            base_header: BlockHeaderAPI,
            transaction: SignedTransactionAPI,
            computation: ComputationAPI,
            state: StateAPI) -> ReceiptAPI:

        gas_used = base_header.gas_used + cls.finalize_gas_used(transaction, computation)

        if computation.is_error:
            status_code = EIP658_TRANSACTION_STATUS_CODE_FAILURE
        else:
            status_code = EIP658_TRANSACTION_STATUS_CODE_SUCCESS

        return transaction.make_receipt(status_code, gas_used, computation.get_log_entries())
