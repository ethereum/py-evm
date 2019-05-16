from abc import ABC, abstractmethod
import functools
from typing import (
    Any,
    Callable,
    Type,
    TypeVar,
    TYPE_CHECKING,
)

from eth_utils import HasExtendedDebugLogger

from eth._utils.datatypes import Configurable

if TYPE_CHECKING:
    from computation import BaseComputation     # noqa: F401


T = TypeVar('T')


class Opcode(Configurable, HasExtendedDebugLogger, ABC):
    mnemonic = None  # type: str
    gas_cost = None  # type: int

    def __init__(self) -> None:
        if self.mnemonic is None:
            raise TypeError("Opcode class {0} missing opcode mnemonic".format(type(self)))
        if self.gas_cost is None:
            raise TypeError("Opcode class {0} missing opcode gas_cost".format(type(self)))

    @abstractmethod
    def __call__(self, computation: 'BaseComputation') -> Any:
        """
        Hook for performing the actual VM execution.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    @classmethod
    def as_opcode(cls: Type[T],
                  logic_fn: Callable[..., Any],
                  mnemonic: str,
                  gas_cost: int) -> Type[T]:
        """
        Class factory method for turning vanilla functions into Opcode classes.
        """
        if gas_cost:
            @functools.wraps(logic_fn)
            def wrapped_logic_fn(computation: 'BaseComputation') -> Any:
                """
                Wrapper functionf or the logic function which consumes the base
                opcode gas cost prior to execution.
                """
                computation.consume_gas(
                    gas_cost,
                    mnemonic,
                )
                return logic_fn(computation)
        else:
            wrapped_logic_fn = logic_fn

        props = {
            '__call__': staticmethod(wrapped_logic_fn),
            'mnemonic': mnemonic,
            'gas_cost': gas_cost,
        }
        opcode_cls = type("opcode:{0}".format(mnemonic), (cls,), props)
        return opcode_cls()

    def __copy__(self) -> 'Opcode':
        return type(self)()

    def __deepcopy__(self, memo: Any) -> 'Opcode':
        return type(self)()


as_opcode = Opcode.as_opcode
