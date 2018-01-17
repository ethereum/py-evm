import os

from evm.utils.module_loading import (
    import_string,
)


def get_gas_estimator(import_path=None):
    if not import_path:
        import_path = os.environ.get(
            'GAS_ESTIMATOR_BACKEND_FUNC',
            'evm.estimators.gas.double_execution_cost',
        )
    return import_string(import_path)
