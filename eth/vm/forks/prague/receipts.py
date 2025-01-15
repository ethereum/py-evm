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
from eth.vm.forks.cancun.constants import (
    BLOB_TX_TYPE,
)
from eth.vm.forks.cancun.receipts import (
    CancunReceiptBuilder,
)
from eth.vm.forks.london.constants import (
    DYNAMIC_FEE_TRANSACTION_TYPE,
)

from ..cancun.receipts import (
    CancunTypedReceipt,
)
from .constants import (
    SET_CODE_TRANSACTION_TYPE,
)


class PragueTypedReceipt(CancunTypedReceipt):
    codecs: Dict[int, Type[Receipt]] = {
        # mypy errors due to Receipt inheriting but not defining abstractmethods
        ACCESS_LIST_TRANSACTION_TYPE: Receipt,  # type: ignore
        DYNAMIC_FEE_TRANSACTION_TYPE: Receipt,  # type: ignore
        BLOB_TX_TYPE: Receipt,  # type: ignore
        SET_CODE_TRANSACTION_TYPE: Receipt,  # type: ignore
    }


class PragueReceiptBuilder(CancunReceiptBuilder):
    typed_receipt_class = PragueTypedReceipt
