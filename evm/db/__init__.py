import os

from evm.utils.module_loading import (
    import_string,
)


DEFAULT_DB_BACKEND = 'evm.db.backends.memory.MemoryDB'


def get_db_backend_class(import_path=None):
    if import_path is None:
        import_path = os.environ.get(
            'CHAIN_DB_BACKEND_CLASS',
            DEFAULT_DB_BACKEND,
        )
    return import_string(import_path)


def get_db_backend(import_path=None, **init_kwargs):
    backend_class = get_db_backend_class(import_path)
    return backend_class(**init_kwargs)
