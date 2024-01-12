from abc import (
    ABC,
)
from typing import (
    Type,
)

from eth_utils import (
    encode_hex,
)
import rlp
from rlp.sedes import (
    CountableList,
)
from eth.abc import (
    BlockHeaderAPI,
    MiningHeaderAPI,
    ReceiptBuilderAPI,
    TransactionBuilderAPI,
)

from ..london.receipts import (
    LondonReceiptBuilder,
)
from .transactions import (
    CancunTransactionBuilder,
)
from ..shanghai.blocks import (
    ShanghaiBackwardsHeader,
    ShanghaiBlock,
)
from ..shanghai.withdrawals import (
    Withdrawal,
)


class CancunMiningHeader(rlp.Serializable, MiningHeaderAPI, ABC):
    pass


class CancunBlockHeader(rlp.Serializable, BlockHeaderAPI, ABC):
    def __str__(self) -> str:
        return f"<CancunBlockHeader #{self.block_number} {encode_hex(self.hash)[2:10]}>"


class CancunBlock(ShanghaiBlock):
    transaction_builder: Type[TransactionBuilderAPI] = CancunTransactionBuilder
    receipt_builder: Type[ReceiptBuilderAPI] = LondonReceiptBuilder
    fields = [
        ("header", CancunBlockHeader),
        ("transactions", CountableList(transaction_builder)),
        ("uncles", CountableList(ShanghaiBackwardsHeader, max_length=0)),
        ("withdrawals", CountableList(Withdrawal)),
    ]
