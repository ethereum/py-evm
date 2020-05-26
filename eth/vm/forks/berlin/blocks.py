from rlp.sedes import (
    CountableList,
)
from eth.rlp.headers import (
    BlockHeader,
)
from eth.vm.forks.muir_glacier.blocks import (
    MuirGlacierBlock,
)

from .transactions import (
    BerlinTransaction,
)


class BerlinBlock(MuirGlacierBlock):
    transaction_class = BerlinTransaction
    fields = [
        ('header', BlockHeader),
        ('transactions', CountableList(transaction_class)),
        ('uncles', CountableList(BlockHeader))
    ]
