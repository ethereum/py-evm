from typing import Type

from rlp.sedes import (
    CountableList,
)

from eth.abc import (
    TransactionBuilderAPI,
)
from eth.rlp.headers import (
    BlockHeader,
)
from eth.vm.forks.muir_glacier.blocks import (
    MuirGlacierBlock,
)

from .transactions import (
    BerlinTransactionBuilder,
)


class BerlinBlock(MuirGlacierBlock):
    transaction_builder: Type[TransactionBuilderAPI] = BerlinTransactionBuilder  # type: ignore
    fields = [
        ('header', BlockHeader),
        ('transactions', CountableList(transaction_builder)),
        ('uncles', CountableList(BlockHeader))
    ]
