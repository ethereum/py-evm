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
from eth.vm.forks.prague.constants import (
    TARGET_BLOB_GAS_PER_BLOCK,
)


def calc_excess_blob_gas_prague(parent_header: BlockHeaderAPI) -> int:
    try:
        if (
            parent_header.excess_blob_gas + parent_header.blob_gas_used
            < TARGET_BLOB_GAS_PER_BLOCK
        ):
            return 0
        else:
            return (
                parent_header.excess_blob_gas
                + parent_header.blob_gas_used
                - TARGET_BLOB_GAS_PER_BLOCK
            )
    except AttributeError:
        return 0


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

    if parent_header is not None:
        all_fields["excess_blob_gas"] = calc_excess_blob_gas_prague(parent_header)

    return PragueBlockHeader(**all_fields)
