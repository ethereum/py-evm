from rlp.sedes import (
    CountableList,
)
from evm.rlp.headers import (
    BlockHeader,
)
from evm.vm.forks.homestead.blocks import (
    HomesteadBlock,
)
from .transactions import (
    SpuriousDragonTransaction,
)


class SpuriousDragonBlock(HomesteadBlock):
    transaction_class = SpuriousDragonTransaction
    fields = [
        ('header', BlockHeader),
        ('transactions', CountableList(transaction_class)),
        ('uncles', CountableList(BlockHeader))
    ]
