import itertools

import rlp

from eth_utils import (
    to_list,
)


@to_list
def get_receipts_from_db(receipt_db, receipt_class):
    for receipt_idx in itertools.count():
        receipt_key = rlp.encode(receipt_idx)
        if receipt_key in receipt_db:
            receipt_data = receipt_db[receipt_key]
            yield rlp.decode(receipt_data, sedes=receipt_class)
        else:
            break
