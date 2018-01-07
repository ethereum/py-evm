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
    ShardingTransaction,
)


class ShardingBlock(HomesteadBlock):
    transaction_class = ShardingTransaction
    fields = [
        ('header', BlockHeader),
        ('transactions', CountableList(transaction_class)),
        ('uncles', CountableList(BlockHeader))
    ]
