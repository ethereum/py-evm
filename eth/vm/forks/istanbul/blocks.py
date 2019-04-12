from rlp.sedes import (
    CountableList,
)
from eth.rlp.headers import (
    BlockHeader,
)
from eth.vm.forks.constantinople.blocks import (
    ConstantinopleBlock,
)

from .transactions import (
    IstanbulTransaction,
)


class IstanbulBlock(ConstantinopleBlock):
    transaction_class = IstanbulTransaction
    fields = [
        ('header', BlockHeader),
        ('transactions', CountableList(transaction_class)),
        ('uncles', CountableList(BlockHeader))
    ]
