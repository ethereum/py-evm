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

    @staticmethod
    def _get_total_blob_gas(transaction: TransactionFieldsAPI) -> int:
        if hasattr(transaction, "blob_versioned_hashes"):
            return GAS_PER_BLOB * len(transaction.blob_versioned_hashes)

        return 0

    def increment_blob_gas_used(
        self, old_header: BlockHeaderAPI, transaction: TransactionFieldsAPI
    ) -> BlockHeaderAPI:
        # This is only relevant for the Cancun fork and later
        return old_header.copy(
            blob_gas_used=old_header.blob_gas_used
            + self._get_total_blob_gas(transaction)
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
        assert block.header.excess_blob_gas == calc_excess_blob_gas(parent_header)

        blob_gas_used = 0

        for tx in block.transactions:
            # modify the check for sufficient balance
            max_total_fee = tx.gas * tx.max_fee_per_gas
            if tx.type_id == BLOB_TX_TYPE:
                max_total_fee += get_total_blob_gas(tx) * tx.max_fee_per_blob_gas
            assert self.state.get_balance(tx.sender) >= max_total_fee

            # add validity logic specific to blob txs
            if tx.type_id == BLOB_TX_TYPE:
                # there must be at least one blob
                assert len(tx.blob_versioned_hashes) > 0

                # all versioned blob hashes must start with VERSIONED_HASH_VERSION_KZG
                for h in tx.blob_versioned_hashes:
                    assert h[0].to_bytes() == VERSIONED_HASH_VERSION_KZG

                # ensure that the user was willing to at least pay the current
                # blob base fee

                # keep track of total blob gas spent in the block
                assert tx.max_fee_per_blob_gas >= self.state.blob_base_fee
                blob_gas_used += get_total_blob_gas(tx)

        # ensure the total blob gas spent is at most equal to the limit
        assert blob_gas_used <= MAX_BLOB_GAS_PER_BLOCK

        # ensure blob_gas_used matches header
        assert block.header.blob_gas_used == blob_gas_used
