from typing import (
    Any,
    Dict,
    Optional,
)

from eth_utils.toolz import (
    curry,
    merge,
)

from eth.abc import (
    BlockHeaderAPI,
)
from eth.constants import (
    EMPTY_SHA256,
)
from eth.vm.forks.cancun import (
    create_cancun_header_from_parent,
)
from eth.vm.forks.prague.blocks import (
    PragueBlockHeader,
)


@curry
def create_prague_header_from_parent(
    parent_header: Optional[BlockHeaderAPI],
    **header_params: Any,
) -> BlockHeaderAPI:
    requests_hash = header_params.pop("requests_hash", EMPTY_SHA256)

    cancun_validated_header = create_cancun_header_from_parent(
        parent_header, **header_params
    )

    all_fields: Dict[Any, Any] = merge(
        cancun_validated_header.as_dict(), {"requests_hash": requests_hash}
    )

    return PragueBlockHeader(**all_fields)
