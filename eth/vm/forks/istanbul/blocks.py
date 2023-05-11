from rlp.sedes import (
    CountableList,
)

from eth.rlp.headers import (
    BlockHeader,
)
from eth.vm.forks.petersburg.blocks import (
    PetersburgBlock,
)

from .transactions import (
    IstanbulTransaction,
)


class IstanbulBlock(PetersburgBlock):
    transaction_builder = IstanbulTransaction
    fields = [
        ("header", BlockHeader),
        ("transactions", CountableList(transaction_builder)),
        ("uncles", CountableList(BlockHeader)),
    ]
