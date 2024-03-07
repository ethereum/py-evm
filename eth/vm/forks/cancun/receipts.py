from typing import (
    Dict,
    Type,
)

from eth.rlp.receipts import (
    Receipt,
)
from eth.vm.forks.berlin.constants import (
    ACCESS_LIST_TRANSACTION_TYPE,
)
from eth.vm.forks.london.constants import (
    DYNAMIC_FEE_TRANSACTION_TYPE,
)

from ..london.receipts import (
    LondonReceiptBuilder,
    LondonTypedReceipt,
)
from .constants import (
    BLOB_TX_TYPE,
)


class CancunTypedReceipt(LondonTypedReceipt):
    codecs: Dict[int, Type[Receipt]] = {
        # mypy errors due to Receipt inheriting but not defining abstractmethods
        ACCESS_LIST_TRANSACTION_TYPE: Receipt,  # type: ignore
        DYNAMIC_FEE_TRANSACTION_TYPE: Receipt,  # type: ignore
        BLOB_TX_TYPE: Receipt,  # type: ignore
    }


class CancunReceiptBuilder(LondonReceiptBuilder):
    typed_receipt_class = CancunTypedReceipt
