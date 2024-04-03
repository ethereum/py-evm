from typing import (
    Type,
)

from eth._utils.db import (
    get_block_header_by_hash,
)
from eth.abc import (
    BlockAPI,
    BlockHeaderAPI,
    StateAPI,
    TransactionFieldsAPI,
)
from eth.rlp.blocks import (
    BaseBlock,
)
from eth.vm.forks.shanghai import (
    ShanghaiVM,
)
from eth.vm.state import (
    BaseState,
)
from eth_utils import (
    ValidationError,
    to_int,
)

from .blocks import (
    CancunBlock,
)
from .constants import (
    BEACON_ROOTS_ADDRESS,
    BEACON_ROOTS_CONTRACT_CODE,
    BLOB_TX_TYPE,
    GAS_PER_BLOB,
    HISTORY_BUFFER_LENGTH,
    MAX_BLOB_GAS_PER_BLOCK,
    VERSIONED_HASH_VERSION_KZG,
)
from .headers import (
    calc_excess_blob_gas,
    create_cancun_header_from_parent,
)
from .state import (
    CancunState,
    get_total_blob_gas,
)


class CancunVM(ShanghaiVM):
    # fork name
    fork = "cancun"

    # classes
    block_class: Type[BaseBlock] = CancunBlock
    _state_class: Type[BaseState] = CancunState

    # methods
    create_header_from_parent = staticmethod(  # type: ignore
        create_cancun_header_from_parent()
    )

    def increment_blob_gas_used(
        self, old_header: BlockHeaderAPI, transaction: TransactionFieldsAPI
    ) -> BlockHeaderAPI:
        return old_header.copy(
            blob_gas_used=old_header.blob_gas_used + get_total_blob_gas(transaction)
        )

    @classmethod
    def block_preprocessing(cls, state: StateAPI, header: BlockHeaderAPI) -> None:
        super().block_preprocessing(state, header)

        parent_beacon_root = header.parent_beacon_block_root

        if state.get_code(BEACON_ROOTS_ADDRESS) == BEACON_ROOTS_CONTRACT_CODE:
            # if the beacon roots contract exists, update the beacon roots
            state.set_storage(
                BEACON_ROOTS_ADDRESS,
                header.timestamp % HISTORY_BUFFER_LENGTH,
                header.timestamp,
            )
            state.set_storage(
                BEACON_ROOTS_ADDRESS,
                header.timestamp % HISTORY_BUFFER_LENGTH + HISTORY_BUFFER_LENGTH,
                to_int(parent_beacon_root),
            )

    def validate_block(self, block: BlockAPI) -> None:
        super().validate_block(block)

        # check that the excess blob gas was updated correctly
        parent_header = get_block_header_by_hash(block.header.parent_hash, self.chaindb)
        if block.header.excess_blob_gas != calc_excess_blob_gas(parent_header):
            raise ValidationError("Block excess blob gas was not updated correctly.")

        blob_gas_used = sum(get_total_blob_gas(tx) for tx in block.transactions)

        # ensure the total blob gas spent is at most equal to the limit
        if blob_gas_used > MAX_BLOB_GAS_PER_BLOCK:
            raise ValidationError("Block exceeded maximum blob gas limit.")

        # ensure blob_gas_used matches header
        block_blob_gas_used = block.header.blob_gas_used
        if block_blob_gas_used != blob_gas_used:
            raise ValidationError(
                f"Block blob gas used ({block_blob_gas_used}) does not match "
                f"total blob gas used ({blob_gas_used})."
            )
