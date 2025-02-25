from hashlib import sha256
from typing import (
    Type,
)

from eth.abc import BlockAPI
from eth.rlp.blocks import (
    BaseBlock,
)
from eth.vm.forks.cancun import (
    CancunVM,
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
