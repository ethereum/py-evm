
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


DEFAULT_BACKEND = PyECCBackend  # type: Type[BaseBLSBackend]

try:
    from .milagro import MilagroBackend
    DEFAULT_BACKEND = MilagroBackend
    AVAILABLE_BACKENDS += (MilagroBackend,)
except ImportError:
    pass

try:
    from .chia import ChiaBackend
    AVAILABLE_BACKENDS += (ChiaBackend,)
except ImportError:
    pass
