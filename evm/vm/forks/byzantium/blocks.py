from rlp.sedes import (
    CountableList,
)
from evm.rlp.headers import (
    BlockHeader,
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
