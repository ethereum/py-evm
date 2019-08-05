import functools

from typing import (
    Any,
    Callable,
    Type,
    TypeVar,
)

from eth._utils.datatypes import Configurable
from eth.abc import (
    ComputationAPI,
    OpcodeAPI,
)


T = TypeVar('T')


def _get_qualname(value: Any) -> str:
    if hasattr(value, '__qualname__'):
        return value.__qualname__
    elif isinstance(value, functools.partial):
        return _get_qualname(value.func)
    else:
        raise Exception(f"Unable to extract __qualname__ from: {value!r}")


class Opcode(Configurable, OpcodeAPI):
    mnemonic: str = None
    gas_cost: int = None

    def __init__(self) -> None:
        if self.mnemonic is None:
            raise TypeError("Opcode class {0} missing opcode mnemonic".format(type(self)))
        if self.gas_cost is None:
            raise TypeError("Opcode class {0} missing opcode gas_cost".format(type(self)))

    @classmethod
    def as_opcode(cls: Type[T],
                  logic_fn: Callable[..., Any],
                  mnemonic: str,
                  gas_cost: int) -> T:
        """
        Class factory method for turning vanilla functions into Opcode classes.
        """
        if gas_cost:
            @functools.wraps(logic_fn)
            def wrapped_logic_fn(computation: ComputationAPI) -> Any:
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
            '__qualname__': _get_qualname(logic_fn),
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
