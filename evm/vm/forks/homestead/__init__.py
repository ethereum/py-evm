from evm.chains.mainnet.constants import (
    DAO_FORK_MAINNET_BLOCK
)
from evm.vm.forks.frontier import FrontierVM

from .headers import (
    create_homestead_header_from_parent,
    compute_homestead_difficulty,
    configure_homestead_header,
)
from .state import HomesteadState


class MetaHomesteadVM(FrontierVM):  # type: ignore
    support_dao_fork = True
    dao_fork_block_number = DAO_FORK_MAINNET_BLOCK


HomesteadVM = MetaHomesteadVM.configure(
    # class name
    __name__='HomesteadVM',
    # fork name
    fork='homestead',
    # classes
    _state_class=HomesteadState,
    # method overrides
    create_header_from_parent=staticmethod(create_homestead_header_from_parent),
    compute_difficulty=staticmethod(compute_homestead_difficulty),
    configure_header=configure_homestead_header,
)
