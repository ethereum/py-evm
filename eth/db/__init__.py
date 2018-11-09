import os
from typing import (
    Any,
    Type,
    cast
)

from eth_utils import import_string

from eth.db.backends.base import BaseAtomicDB


DEFAULT_DB_BACKEND = 'eth.db.atomic.AtomicDB'


def get_db_backend_class(import_path: str = None) -> Type[BaseAtomicDB]:
    if import_path is None:
        import_path = os.environ.get(
            'CHAIN_DB_BACKEND_CLASS',
            DEFAULT_DB_BACKEND,
        )
    return cast(Type[BaseAtomicDB], import_string(import_path))


def get_db_backend(import_path: str = None, **init_kwargs: Any) -> BaseAtomicDB:
    backend_class = get_db_backend_class(import_path)
    return backend_class(**init_kwargs)
