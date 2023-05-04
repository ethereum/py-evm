from rlp.sedes import (
    CountableList,
)

from eth.rlp.headers import (
    BlockHeader,
)
from eth.vm.forks.spurious_dragon.blocks import (
    SpuriousDragonBlock,
)

from .transactions import (
    ByzantiumTransaction,
)


class ByzantiumBlock(SpuriousDragonBlock):
    transaction_builder = ByzantiumTransaction
    fields = [
        ("header", BlockHeader),
        ("transactions", CountableList(transaction_builder)),
        ("uncles", CountableList(BlockHeader)),
    ]
