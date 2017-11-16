from rlp.sedes import (
    CountableList,
)
from evm.rlp.headers import (
    BlockHeader,
)
from evm.rlp.receipts import (
    Receipt,
)
from evm.vm.forks.spurious_dragon.blocks import (
    SpuriousDragonBlock,
)

from .transactions import (
    ByzantiumTransaction,
)


class ByzantiumBlock(SpuriousDragonBlock):
    transaction_class = ByzantiumTransaction
    fields = [
        ('header', BlockHeader),
        ('transactions', CountableList(transaction_class)),
        ('uncles', CountableList(BlockHeader))
    ]

    def make_receipt(self, transaction, computation):
        old_receipt = super(ByzantiumBlock, self).make_receipt(transaction, computation)
        receipt = Receipt(
            state_root=b'' if computation.error else b'\x01',
            gas_used=old_receipt.gas_used,
            logs=old_receipt.logs,
        )
        return receipt
