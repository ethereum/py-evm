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
from eth.vm.forks.berlin.receipts import (
    BerlinReceiptBuilder,
    TypedReceipt as BerlinTypedReceipt,
)

from .constants import (
    DYNAMIC_FEE_TRANSACTION_TYPE,
)


class LondonTypedReceipt(BerlinTypedReceipt):
    codecs: Dict[int, Type[Receipt]] = {
        # mypy errors due to Receipt inheriting but not defining abstractmethods
        ACCESS_LIST_TRANSACTION_TYPE: Receipt,  # type: ignore
        DYNAMIC_FEE_TRANSACTION_TYPE: Receipt,  # type: ignore
    }


class LondonReceiptBuilder(BerlinReceiptBuilder):
    typed_receipt_class = LondonTypedReceipt
