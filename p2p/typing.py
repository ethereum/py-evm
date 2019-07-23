from typing import Any, Dict, List, Tuple, Union

from mypy_extensions import TypedDict

import rlp


class TypedDictPayload(TypedDict):
    pass


PayloadType = Union[
    Dict[str, Any],
    List[rlp.Serializable],
    Tuple[rlp.Serializable, ...],
    TypedDictPayload,
]


StructureType = Union[
    Tuple[Tuple[str, Any], ...],
]


CapabilityType = Tuple[str, int]
CapabilitiesType = Tuple[CapabilityType, ...]
