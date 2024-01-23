from typing import (
    Type,
)

from eth.abc import (
    BlockHeaderAPI,
    StateAPI,
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
    HISTORY_BUFFER_LENGTH,
)
from .headers import (
    configure_cancun_header,
    create_cancun_header_from_parent,
)
from .state import (
    CancunState,
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
    configure_header = configure_cancun_header

    @classmethod
    def block_preprocessing(cls, state: StateAPI, header: BlockHeaderAPI) -> None:
        super().block_preprocessing(state, header)

        parent_beacon_root = header.parent_beacon_block_root

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
