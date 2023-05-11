from rlp.sedes import (
    CountableList,
)

from eth.rlp.headers import (
    BlockHeader,
)
from eth.vm.forks.frontier.blocks import (
    FrontierBlock,
)

from .transactions import (
    HomesteadTransaction,
)


class HomesteadBlock(FrontierBlock):
    transaction_builder = HomesteadTransaction
    fields = [
        ("header", BlockHeader),
        ("transactions", CountableList(transaction_builder)),
        ("uncles", CountableList(BlockHeader)),
    ]
