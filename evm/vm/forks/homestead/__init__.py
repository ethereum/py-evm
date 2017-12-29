from evm.chains.mainnet.constants import (
    DAO_FORK_BLOCK_NUMBER
)

from ..frontier import FrontierVM

from .opcodes import HOMESTEAD_OPCODES
from .blocks import HomesteadBlock
from .computation import HomesteadComputation
from .validation import validate_homestead_transaction
from .headers import (
    create_homestead_header_from_parent,
    configure_homestead_header,
)


class MetaHomesteadVM(FrontierVM):
    support_dao_fork = True
    dao_fork_block_number = DAO_FORK_BLOCK_NUMBER


HomesteadVM = MetaHomesteadVM.configure(
    name='HomesteadVM',
    opcodes=HOMESTEAD_OPCODES,
    _block_class=HomesteadBlock,
    _computation_class=HomesteadComputation,
    # method overrides
    validate_transaction=validate_homestead_transaction,
    create_header_from_parent=staticmethod(create_homestead_header_from_parent),
    configure_header=configure_homestead_header,
)
