from typing import (
    Any,
    Optional,
)

from toolz import (
    curry,
)

from eth.abc import (
    BlockHeaderAPI,
)
from eth.constants import (
    BLANK_ROOT_HASH,
)
from eth.vm.forks.byzantium.headers import (
    configure_header,
)
from eth.vm.forks.paris.headers import (
    create_paris_header_from_parent,
)

from .blocks import (
    ShanghaiBlockHeader,
)


@curry
def create_shanghai_header_from_parent(
    parent_header: Optional[BlockHeaderAPI],
    **header_params: Any,
) -> BlockHeaderAPI:
    # remove new fields if present
    withdrawals_root = header_params.pop("withdrawals_root", BLANK_ROOT_HASH)

    paris_validated_header = create_paris_header_from_parent(
        parent_header, **header_params
    )

    # put new fields back in
    all_fields = {
        **paris_validated_header.as_dict(),
        "withdrawals_root": withdrawals_root,
    }
    return ShanghaiBlockHeader(**all_fields)


configure_shanghai_header = configure_header()
