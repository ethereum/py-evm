from typing import (
    Any,
    Callable,
    Type,
    TypeVar,
)

from eth_utils import (
    ExtendedDebugLogger,
    get_extended_debug_logger,
)

from eth._utils.datatypes import (
    Configurable,
)
from eth.abc import (
    ComputationAPI,
    OpcodeAPI,
)

T = TypeVar("T")


class _FastOpcode(OpcodeAPI):
    __slots__ = ("logic_fn", "mnemonic", "gas_cost")

    def __init__(
        self, logic_fn: Callable[..., Any], mnemonic: str, gas_cost: int
    ) -> None:
        self.logic_fn = logic_fn
        self.mnemonic = mnemonic
        self.gas_cost = gas_cost

    def __call__(self, computation: ComputationAPI) -> None:
        computation.consume_gas(self.gas_cost, self.mnemonic)
        return self.logic_fn(computation)

    @classmethod
    def as_opcode(
        cls: Type["_FastOpcode"],
        logic_fn: Callable[..., Any],
        mnemonic: str,
        gas_cost: int,
    ) -> OpcodeAPI:
        return cls(logic_fn, mnemonic, gas_cost)


class Opcode(Configurable, OpcodeAPI):
    mnemonic: str = None
    gas_cost: int = None

    def __init__(self) -> None:
        if self.mnemonic is None:
            raise TypeError(f"Opcode class {type(self)} missing opcode mnemonic")
        if self.gas_cost is None:
            raise TypeError(f"Opcode class {type(self)} missing opcode gas_cost")

    @property
    def logger(self) -> ExtendedDebugLogger:
        return get_extended_debug_logger(f"eth.vm.logic.{self.mnemonic}")

    @classmethod
    def as_opcode(
        cls: Type[T], logic_fn: Callable[..., Any], mnemonic: str, gas_cost: int
    ) -> OpcodeAPI:
        return _FastOpcode(logic_fn, mnemonic, gas_cost)


as_opcode = Opcode.as_opcode
