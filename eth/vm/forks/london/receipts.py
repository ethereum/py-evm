from typing import (
    Dict,
    Type,
)

from eth.rlp.receipts import (
    Receipt,
)
from eth.vm.forks.berlin.receipts import (
    BerlinReceiptBuilder
)
from eth.vm.forks.berlin.constants import (
    ACCESS_LIST_TRANSACTION_TYPE,
)

from .constants import DYNAMIC_FEE_TRANSACTION_TYPE


class LondonReceiptBuilder(BerlinReceiptBuilder):
    codecs: Dict[int, Type[Receipt]] = {
        ACCESS_LIST_TRANSACTION_TYPE: Receipt,
        DYNAMIC_FEE_TRANSACTION_TYPE: Receipt,
    }
