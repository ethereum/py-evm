import os

from evm.utils.module_loading import (
    import_string,
)


DEFAULT_ECC_BACKEND = 'evm.ecc.backends.pure_python.PurePythonECCBackend'


def get_ecc_backend_class(import_path=None):
    if import_path is None:
        import_path = os.environ.get(
            'CHAIN_ECC_BACKEND_CLASS',
            DEFAULT_ECC_BACKEND,
        )
    return import_string(import_path)


def get_ecc_backend(import_path=None):
    backend_class = get_ecc_backend_class(import_path)
    return backend_class()
