import os
from typing import (
    Callable,
    cast,
    Union,
)

from eth.rlp.transactions import (
    BaseTransaction,
)
from eth.utils.module_loading import (
    import_string,
)
from eth.utils.spoof import (
    SpoofTransaction,
)
from eth.vm.state import (
    BaseState,
)


def get_gas_estimator() -> Callable[[BaseState, Union[BaseTransaction, SpoofTransaction]], int]:
    import_path = os.environ.get(
        'GAS_ESTIMATOR_BACKEND_FUNC',
        'eth.estimators.gas.binary_gas_search_intrinsic_tolerance',
    )
    return cast(
        Callable[[BaseState, Union[BaseTransaction, SpoofTransaction]], int],
        import_string(import_path)
    )
