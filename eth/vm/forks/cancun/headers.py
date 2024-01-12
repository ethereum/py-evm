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
from eth.vm.forks.shanghai.headers import (
    create_shanghai_header_from_parent,
)

from .blocks import (
    CancunBlockHeader,
)


@curry
def create_cancun_header_from_parent(
    parent_header: Optional[BlockHeaderAPI],
    **header_params: Any,
) -> BlockHeaderAPI:
    shanghai_validated_header = create_shanghai_header_from_parent(
        parent_header, **header_params
    )

    # extract params validated up to shanghai (previous VM)
    # and plug into a `CancunBlockHeader` class
    all_fields = shanghai_validated_header.as_dict()
    return CancunBlockHeader(**all_fields)


configure_cancun_header = configure_header()
