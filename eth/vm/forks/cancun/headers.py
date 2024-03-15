from typing import (
    Any,
    Optional,
)

from toolz import (
    curry,
    merge,
)

from eth.abc import (
    BlockHeaderAPI,
)
from eth.constants import (
    BLANK_ROOT_HASH,
)
from eth.vm.forks.cancun.constants import (
    TARGET_BLOB_GAS_PER_BLOCK,
)
from eth.vm.forks.shanghai.headers import (
    create_shanghai_header_from_parent,
)

from .blocks import (
    CancunBlockHeader,
)


def calc_excess_blob_gas(parent_header: BlockHeaderAPI) -> int:
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
        # parent is a non-Cancun header
        return 0


@curry
def create_cancun_header_from_parent(
    parent_header: Optional[BlockHeaderAPI],
    **header_params: Any,
) -> BlockHeaderAPI:
    # remove new fields if present
    excess_blob_gas = header_params.pop("excess_blob_gas", 0)
    blob_gas_used = header_params.pop("blob_gas_used", 0)
    parent_beacon_block_root = header_params.pop(
        "parent_beacon_block_root", BLANK_ROOT_HASH
    )

    shanghai_validated_header = create_shanghai_header_from_parent(
        parent_header, **header_params
    )

    # put new fields back in
    all_fields = merge(
        shanghai_validated_header.as_dict(),
        {
            "blob_gas_used": blob_gas_used,
            "excess_blob_gas": excess_blob_gas,
            "parent_beacon_block_root": parent_beacon_block_root,
        },
    )

    if parent_header is not None:
        all_fields["excess_blob_gas"] = calc_excess_blob_gas(parent_header)

    return CancunBlockHeader(**all_fields)
