from typing import Optional, Type

from eth_typing import BlockNumber

from eth.abc import (
    BlockAPI,
    StateAPI,
)
from eth.vm.forks.frontier import FrontierVM

from .blocks import HomesteadBlock
from .headers import (
    create_homestead_header_from_parent,
    compute_homestead_difficulty,
    configure_homestead_header,
)
from .state import HomesteadState


class MetaHomesteadVM(FrontierVM):
    support_dao_fork = True
    _dao_fork_block_number: Optional[BlockNumber] = None

    @classmethod
    def get_dao_fork_block_number(cls) -> BlockNumber:
        if cls._dao_fork_block_number is None:
            raise TypeError(
                "HomesteadVM must be configured with a valid `_dao_fork_block_number`"
            )
        return cls._dao_fork_block_number


class HomesteadVM(MetaHomesteadVM):
    # fork name
    fork: str = "homestead"

    # classes
    block_class: Type[BlockAPI] = HomesteadBlock
    _state_class: Type[StateAPI] = HomesteadState

    # method overrides
    create_header_from_parent = staticmethod(create_homestead_header_from_parent)  # type: ignore  # noqa: E501
    compute_difficulty = staticmethod(compute_homestead_difficulty)  # type: ignore
    configure_header = configure_homestead_header
