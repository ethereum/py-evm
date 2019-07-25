from typing import Any, Dict, List, Tuple, Union

from mypy_extensions import TypedDict

import rlp


class TypedDictPayload(TypedDict):
    pass


Payload = Union[
    Dict[str, Any],
    List[rlp.Serializable],
    Tuple[rlp.Serializable, ...],
    TypedDictPayload,
]


Structure = Union[
    Tuple[Tuple[str, Any], ...],
]


Capability = Tuple[str, int]
Capabilities = Tuple[Capability, ...]
