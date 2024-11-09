from typing import (
    Any,
    Dict,
    Optional,
)

from toolz import (
    curry,
)

from eth.abc import (
    BlockHeaderAPI,
)
from eth.rlp.headers import (
    BlockHeader,
)


@curry
def create_prague_header_from_parent(
    parent_header: Optional[BlockHeaderAPI],
    **header_params: Any,
) -> BlockHeaderAPI:
    all_fields: Dict[Any, Any] = {}

    return BlockHeader(**all_fields)
