from typing import Tuple, Type  # noqa: F401

from .base import BaseBLSBackend  # noqa: F401
from .noop import NoOpBackend
from .py_ecc import PyECCBackend

AVAILABLE_BACKENDS = (
    NoOpBackend,
    PyECCBackend,
)  # type: Tuple[Type[BaseBLSBackend], ...]


DEFAULT_BACKEND = PyECCBackend  # type: Type[BaseBLSBackend]

try:
    from .milagro import MilagroBackend

    DEFAULT_BACKEND = MilagroBackend
    AVAILABLE_BACKENDS += (MilagroBackend,)
except ImportError:
    pass
