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
        ACCESS_LIST_TRANSACTION_TYPE: Receipt,
        DYNAMIC_FEE_TRANSACTION_TYPE: Receipt,
    }


class LondonReceiptBuilder(BerlinReceiptBuilder):
    typed_receipt_class = LondonTypedReceipt
