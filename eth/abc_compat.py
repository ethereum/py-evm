# mypy: warn-unused-ignores=0
# (piper) We have to disable this warning because mypy doesn't think the type
# ignores are needed in python3.7 but they do end up being required in
# python3.6
from abc import ABCMeta
import sys
from typing import (
    ContextManager,
    MutableMapping,
    TYPE_CHECKING,
)

from eth_utils import (
    ExtendedDebugLogger,
    HasExtendedDebugLoggerMeta,
)

if TYPE_CHECKING:
    from .abc import (  # noqa: F401
        ComputationAPI,
    )


ABCWithLoggerMeta = HasExtendedDebugLoggerMeta.meta_compat(ABCMeta)


# mypy doesn't recognize ABCWithLoggerMeta as a valid metaclass
class ABCWithLogger(metaclass=ABCWithLoggerMeta):  # type: ignore
    logger: ExtendedDebugLogger


if sys.version_info < (3, 7):
    from typing import GenericMeta

    GenericABCWithLogger = ABCWithLoggerMeta.meta_compat(GenericMeta)


if sys.version_info < (3, 7):
    # mypy doesn't recognize MutableMappingWithLoggerMeta as a valid metaclass
    class DatabaseAPIBase(MutableMapping[bytes, bytes], metaclass=GenericABCWithLogger):  # type: ignore  # noqa: E501
        logger: ExtendedDebugLogger
else:
    class DatabaseAPIBase(MutableMapping[bytes, bytes], ABCWithLogger):
        pass


if sys.version_info < (3, 7):
    # mypy doesn't recognize MutableMappingWithLoggerMeta as a valid metaclass
    class ComputationAPIBase(ContextManager['ComputationAPI'], metaclass=GenericABCWithLogger):  # type: ignore  # noqa: E501
        logger: ExtendedDebugLogger
else:
    class ComputationAPIBase(ContextManager['ComputationAPI'], ABCWithLogger):  # noqa: E501
        pass
