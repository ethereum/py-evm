from typing import Any, Tuple, TypeVar, Union


TCommandPayload = TypeVar('TCommandPayload')


Structure = Union[
    Tuple[Tuple[str, Any], ...],
]


Capability = Tuple[str, int]
Capabilities = Tuple[Capability, ...]
