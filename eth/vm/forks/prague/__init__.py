from hashlib import sha256
from typing import (
    Type,
)

from eth._utils.db import (
    get_block_header_by_hash,
)
from eth.abc import (
    BlockAPI,
)
from eth.rlp.blocks import (
    BaseBlock,
)
from eth.vm.forks.cancun import (
    CancunVM,
    get_total_blob_gas,
)
from eth.vm.forks.prague.constants import (
    HISTORY_SERVE_WINDOW,
    HISTORY_STORAGE_ADDRESS,
    HISTORY_STORAGE_CONTRACT_CODE,
    MAX_BLOB_GAS_PER_BLOCK,
)
from eth.vm.state import (
    BaseState,
)
from eth_utils import ValidationError

from .blocks import (
    PragueBlock,
)
from .headers import (
    calc_excess_blob_gas_prague,
    create_prague_header_from_parent,
)
from .state import (
    PragueState,
)


class PragueVM(CancunVM):
    # fork name
    fork = "prague"

    # classes
    block_class: Type[BaseBlock] = PragueBlock
    _state_class: Type[BaseState] = PragueState

    # methods
    create_header_from_parent = staticmethod(  # type: ignore
        create_prague_header_from_parent()
    )

    @staticmethod
    def compute_requests_hash(block: BlockAPI) -> BlockAPI:
        m = sha256()
        for r in block.block_requests:
            if len(r) > 1:
                m.update(sha256(r).digest())

        updated_header = block.header.copy(requests_hash=m.digest())
        return block.copy(header=updated_header)

    def block_preprocessing(self, block: BlockAPI) -> None:
        super().block_preprocessing(block)

        if (
            self.state.get_code(HISTORY_STORAGE_ADDRESS)
            == HISTORY_STORAGE_CONTRACT_CODE
        ):
            # if the history storage contract exists, update the with the parent hash
            self.state.set_storage(
                HISTORY_STORAGE_ADDRESS,
                (block.number - 1) % HISTORY_SERVE_WINDOW,
                int.from_bytes(block.header.parent_hash, "big"),
            )

    def validate_block_blobs(self, block: BlockAPI) -> None:
        # check that the excess blob gas was updated correctly
        parent_header = get_block_header_by_hash(block.header.parent_hash, self.chaindb)
        if block.header.excess_blob_gas != calc_excess_blob_gas_prague(parent_header):
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
