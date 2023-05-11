from rlp.sedes import (
    CountableList,
)

from eth.rlp.headers import (
    BlockHeader,
)
from eth.vm.forks.byzantium.blocks import (
    ByzantiumBlock,
)

from .transactions import (
    ConstantinopleTransaction,
)


class ConstantinopleBlock(ByzantiumBlock):
    transaction_builder = ConstantinopleTransaction
    fields = [
        ("header", BlockHeader),
        ("transactions", CountableList(transaction_builder)),
        ("uncles", CountableList(BlockHeader)),
    ]
