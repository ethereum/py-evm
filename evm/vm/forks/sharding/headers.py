from evm.constants import (
    EMPTY_SHA3,
)
from evm.vm.forks.byzantium.headers import (
    create_byzantium_header_from_parent,
)


def create_sharding_header_from_parent(parent_header, **header_params):
    if 'transaction_root' not in header_params:
        header_params['transaction_root'] = EMPTY_SHA3
    if 'receipt_root' not in header_params:
        header_params['receipt_root'] = EMPTY_SHA3
    return create_byzantium_header_from_parent(parent_header, **header_params)
