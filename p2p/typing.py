from typing import Any, Dict, Sequence, Tuple, Union

from mypy_extensions import TypedDict

import rlp


class TypedDictPayload(TypedDict):
    pass


Payload = Union[
    Dict[str, Any],
    Sequence[rlp.Serializable],
    TypedDictPayload,
]


Structure = Union[
    Tuple[Tuple[str, Any], ...],
]


Capability = Tuple[str, int]
Capabilities = Tuple[Capability, ...]
