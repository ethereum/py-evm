from typing import (
    Dict,
    Type,
)

from eth.rlp.receipts import (
    Receipt,
    ReceiptAPI,
)
from eth.vm.forks.berlin.receipts import (
    BerlinReceiptBuilder
)
from eth.vm.forks.berlin.constants import (
    ACCESS_LIST_TRANSACTION_TYPE,
)

from .constants import BASE_GAS_FEE_TRANSACTION_TYPE


class LondonReceiptBuilder(BerlinReceiptBuilder):
    codecs: Dict[int, Type[ReceiptAPI]] = {
        ACCESS_LIST_TRANSACTION_TYPE: Receipt,
        BASE_GAS_FEE_TRANSACTION_TYPE: Receipt,
    }
