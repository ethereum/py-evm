from evm.vm import BaseEVM

from .opcodes import FRONTIER_OPCODES
from .transactions import FrontierTransaction
from .blocks import FrontierBlock
from .validation import validate_frontier_transaction


FrontierEVM = BaseEVM.configure(
    name='FrontierEVM',
    opcodes=FRONTIER_OPCODES,
    transaction_class=FrontierTransaction,
    block_class=FrontierBlock,
    # method overrides
    validate_transaction=validate_frontier_transaction,
)
