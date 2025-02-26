from hashlib import sha256
from typing import (
    Type,
)

from eth.abc import (
    BlockAPI,
)
from eth.rlp.blocks import (
    BaseBlock,
)
from eth.vm.forks.cancun import (
    CancunVM,
)
from eth.vm.forks.prague.constants import (
    HISTORY_SERVE_WINDOW,
    HISTORY_STORAGE_ADDRESS,
    HISTORY_STORAGE_CONTRACT_CODE,
)
from eth.vm.state import (
    BaseState,
)

from .blocks import (
    PragueBlock,
)
from .headers import (
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
            state.set_storage(
                HISTORY_STORAGE_ADDRESS,
                (block.number - 1) % HISTORY_SERVE_WINDOW,
                int.from_bytes(block.header.parent_hash, "big"),
            )
