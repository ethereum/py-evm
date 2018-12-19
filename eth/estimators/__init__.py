import os
from typing import (
    Callable,
    cast,
)

from eth.typing import (
    BaseOrSpoofTransaction,
)
from eth._utils.module_loading import (
    import_string,
)
from eth.vm.state import (
    BaseState,
)


def get_gas_estimator() -> Callable[[BaseState, BaseOrSpoofTransaction], int]:
    import_path = os.environ.get(
        'GAS_ESTIMATOR_BACKEND_FUNC',
        'eth.estimators.gas.binary_gas_search_intrinsic_tolerance',
    )
    return cast(
        Callable[[BaseState, BaseOrSpoofTransaction], int],
        import_string(import_path)
    )
