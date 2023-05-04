from rlp.sedes import (
    CountableList,
)

from eth.rlp.headers import (
    BlockHeader,
)
from eth.vm.forks.homestead.blocks import (
    HomesteadBlock,
)

from .transactions import (
    SpuriousDragonTransaction,
)


class SpuriousDragonBlock(HomesteadBlock):
    transaction_builder = SpuriousDragonTransaction
    fields = [
        ("header", BlockHeader),
        ("transactions", CountableList(transaction_builder)),
        ("uncles", CountableList(BlockHeader)),
    ]
