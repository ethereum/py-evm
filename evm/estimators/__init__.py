import os

from evm.utils.module_loading import (
    import_string,
)


def get_gas_estimator():
    import_path = os.environ.get(
        'GAS_ESTIMATOR_BACKEND_FUNC',
        'evm.estimators.gas.binary_gas_search_intrinsic_tolerance',
    )
    return import_string(import_path)
