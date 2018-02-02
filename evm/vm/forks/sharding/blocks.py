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

    transaction_fee_sum = None

    def __init__(self, header, transactions=None, uncles=None):
        self.transaction_fee_sum = 0

        super(ShardingBlock, self).__init__(
            header=header,
            transactions=transactions,
            uncles=uncles,
        )
