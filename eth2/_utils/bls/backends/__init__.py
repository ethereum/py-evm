
from .noop import NoOpBackend
from .py_ecc import PyECCBackend
from .base import BaseBLSBackend  # noqa: F401
from typing import (  # noqa: F401
    Type,
    Tuple,
)


AVAILABLE_BACKENDS = (
    NoOpBackend,
    PyECCBackend,
)  # type: Tuple[Type[BaseBLSBackend], ...]

# If blspy not installed, use PyECC as default BLS backend

DEFAULT_BACKEND = None  # type: Type[BaseBLSBackend]

try:
    from .chia import ChiaBackend
    DEFAULT_BACKEND = ChiaBackend
    AVAILABLE_BACKENDS += (ChiaBackend,)
except ImportError:
    DEFAULT_BACKEND = PyECCBackend
