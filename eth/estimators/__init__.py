import os
from typing import (
    Any,
)

from eth.utils.module_loading import (
    import_string,
)


def get_gas_estimator() -> Any:
    import_path = os.environ.get(
        'GAS_ESTIMATOR_BACKEND_FUNC',
        'eth.estimators.gas.binary_gas_search_intrinsic_tolerance',
    )
    return import_string(import_path)
