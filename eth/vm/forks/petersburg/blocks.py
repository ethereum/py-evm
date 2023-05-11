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
    PetersburgTransaction,
)


class PetersburgBlock(ByzantiumBlock):
    transaction_builder = PetersburgTransaction
    fields = [
        ("header", BlockHeader),
        ("transactions", CountableList(transaction_builder)),
        ("uncles", CountableList(BlockHeader)),
    ]
