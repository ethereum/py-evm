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
from eth.vm.forks.cancun.blocks import (
    CancunBlock,
)

from ..shanghai.withdrawals import (
    Withdrawal,
)
from .receipts import (
    PragueReceiptBuilder,
)
from .transactions import (
    PragueTransactionBuilder,
)


class PragueBlock(CancunBlock):
    transaction_builder: Type[TransactionBuilderAPI] = PragueTransactionBuilder
    receipt_builder: Type[ReceiptBuilderAPI] = PragueReceiptBuilder
    fields = [
        ("header", BlockHeader),
        ("transactions", CountableList(transaction_builder)),
        ("uncles", CountableList(None, max_length=0)),
        ("withdrawals", CountableList(Withdrawal)),
    ]
