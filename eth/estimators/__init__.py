import os
from typing import (
    Callable,
    cast,
)

from eth.abc import (
    SignedTransactionAPI,
    StateAPI,
)
from eth._utils.module_loading import (
    import_string,
)


def get_gas_estimator() -> Callable[[StateAPI, SignedTransactionAPI], int]:
    import_path = os.environ.get(
        "GAS_ESTIMATOR_BACKEND_FUNC",
        "eth.estimators.gas.binary_gas_search_intrinsic_tolerance",
    )
    return cast(
        Callable[[StateAPI, SignedTransactionAPI], int], import_string(import_path)
    )
