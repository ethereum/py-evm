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
    paris_validated_header = create_paris_header_from_parent(
        parent_header, **header_params
    )

    # extract params validated up to paris (previous VM)
    # and plug into a `ShanghaiBlockHeader` class
    all_fields = paris_validated_header.as_dict()
    return ShanghaiBlockHeader(**all_fields)


configure_shanghai_header = configure_header()
