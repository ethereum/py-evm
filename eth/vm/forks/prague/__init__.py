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
from eth.vm.forks.cancun import (
    CancunVM,
)
from eth.vm.state import (
    BaseState,
)
from eth_utils import (
    ValidationError,
    to_int,
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
