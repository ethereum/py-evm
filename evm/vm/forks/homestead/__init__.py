from typing import Type  # noqa: F401
from evm.rlp.blocks import BaseBlock  # noqa: F401
from evm.vm.state import BaseState  # noqa: F401

from evm.chains.mainnet.constants import (
    DAO_FORK_MAINNET_BLOCK
)
from evm.vm.forks.frontier import FrontierVM

from .blocks import HomesteadBlock
from .headers import (
    create_homestead_header_from_parent,
    compute_homestead_difficulty,
    configure_homestead_header,
)
from .state import HomesteadState


class MetaHomesteadVM(FrontierVM):
    support_dao_fork = True
    dao_fork_block_number = DAO_FORK_MAINNET_BLOCK


class HomesteadVM(MetaHomesteadVM):
    # fork name
    fork = 'homestead'  # type: str

    # classes
    block_class = HomesteadBlock  # type: Type[BaseBlock]
    _state_class = HomesteadState  # type: Type[BaseState]

    # method overrides
    create_header_from_parent = staticmethod(create_homestead_header_from_parent)
    compute_difficulty = staticmethod(compute_homestead_difficulty)
    configure_header = configure_homestead_header
