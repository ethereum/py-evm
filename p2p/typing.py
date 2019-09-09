from typing import Any, Dict, Sequence, Tuple, TypeVar, Union

from mypy_extensions import TypedDict

import rlp


class TypedDictPayload(TypedDict):
    pass


Payload = Union[
    Dict[str, Any],
    Sequence[rlp.Serializable],
    TypedDictPayload,
]


# A payload to be delivered with a request
TRequestPayload = TypeVar('TRequestPayload', bound=Payload, covariant=True)
# A payload to be delivered as a response
TResponsePayload = TypeVar('TResponsePayload', bound=Payload)


Structure = Union[
    Tuple[Tuple[str, Any], ...],
]


Capability = Tuple[str, int]
Capabilities = Tuple[Capability, ...]
