from rlp.sedes import (
    CountableList,
)

from eth.rlp.headers import (
    BlockHeader,
)
from eth.vm.forks.istanbul.blocks import (
    IstanbulBlock,
)

from .transactions import (
    MuirGlacierTransaction,
)


class MuirGlacierBlock(IstanbulBlock):
    transaction_builder = MuirGlacierTransaction
    fields = [
        ("header", BlockHeader),
        ("transactions", CountableList(transaction_builder)),
        ("uncles", CountableList(BlockHeader)),
    ]
