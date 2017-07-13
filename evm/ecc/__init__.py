import os
from ..utils.module_loading import (
    import_string,
)


def get_ecc_backend_class(import_path=None):
    if import_path is None:
        import_path = os.environ.get('EVM_ECC_BACKEND_CLASS',
                                     'evm.ecc.backends.pure_python_ecc_backend.PurePythonECCBackend'
                                     )
    return import_string(import_path)


def get_ecc_backend():
    backend_class = get_ecc_backend_class()
    return backend_class()
