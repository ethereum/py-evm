from typing import (
    Type,
)

from rlp.sedes import (
    CountableList,
)

from eth.abc import (
    ReceiptBuilderAPI,
    TransactionBuilderAPI,
)
from eth.rlp.headers import (
    BlockHeader,
)
from eth.vm.forks.muir_glacier.blocks import (
    MuirGlacierBlock,
)

from .receipts import (
    BerlinReceiptBuilder,
)
from .transactions import (
    BerlinTransactionBuilder,
)


class BerlinBlock(MuirGlacierBlock):
    transaction_builder: Type[TransactionBuilderAPI] = BerlinTransactionBuilder  # type: ignore  # noqa: E501
    receipt_builder: Type[ReceiptBuilderAPI] = BerlinReceiptBuilder  # type: ignore
    fields = [
        ("header", BlockHeader),
        ("transactions", CountableList(transaction_builder)),
        ("uncles", CountableList(BlockHeader)),
    ]
