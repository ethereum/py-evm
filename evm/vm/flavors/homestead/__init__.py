from evm.vm import BaseEVM

from .opcodes import HOMESTEAD_OPCODES
from .transactions import HomesteadTransaction
from .blocks import HomesteadBlock
from .validation import validate_homestead_transaction


HomesteadEVM = BaseEVM.configure(
    name='HomesteadEVM',
    opcodes=HOMESTEAD_OPCODES,
    transaction_class=HomesteadTransaction,
    block_class=HomesteadBlock,
    # method overrides
    validate_transaction=validate_homestead_transaction,
)
