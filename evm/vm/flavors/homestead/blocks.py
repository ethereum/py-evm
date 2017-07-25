from rlp.sedes import (
    CountableList,
)
from evm.rlp.headers import (
    BlockHeader,
)
from evm.vm.flavors.frontier.blocks import (
    FrontierBlock,
)
from .transactions import (
    HomesteadTransaction,
)


class HomesteadBlock(FrontierBlock):
    transaction_class = HomesteadTransaction
    fields = [
        ('header', BlockHeader),
        ('transactions', CountableList(HomesteadTransaction)),
        ('uncles', CountableList(BlockHeader))
    ]
