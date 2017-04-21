from evm.vm.flavors.frontier.blocks import (
    OpenFrontierBlock,
    SealedFrontierBlock,
)
from .transactions import (
    HomesteadTransaction,
)


class SealedHomesteadBlock(SealedFrontierBlock):
    pass


class OpenHomesteadBlock(OpenFrontierBlock):
    transaction_class = HomesteadTransaction
    sealed_block_class = SealedHomesteadBlock
