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
from .vm_state import HomesteadVMState


class MetaHomesteadVM(FrontierVM):
    support_dao_fork = True
    dao_fork_block_number = DAO_FORK_MAINNET_BLOCK


HomesteadVM = MetaHomesteadVM.configure(
    __name__='HomesteadVM',
    # classes
    _block_class=HomesteadBlock,
    _state_class=HomesteadVMState,
    # method overrides
    create_header_from_parent=staticmethod(create_homestead_header_from_parent),
    compute_difficulty=staticmethod(compute_homestead_difficulty),
    configure_header=configure_homestead_header,
)
