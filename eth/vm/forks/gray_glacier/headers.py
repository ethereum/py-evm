from typing import (
    Any,
    Callable,
    Optional,
)

from toolz import (
    curry,
)

from eth.abc import (
    BlockHeaderAPI,
)
from eth.vm.forks.arrow_glacier.headers import (
    create_arrow_glacier_header_from_parent,
)
from eth.vm.forks.byzantium.headers import (
    compute_difficulty,
    configure_header,
)

from .blocks import (
    GrayGlacierBlockHeader,
)

compute_gray_glacier_difficulty = compute_difficulty(11_400_000)
configure_gray_glacier_header = configure_header(
    difficulty_fn=compute_gray_glacier_difficulty
)


@curry
def create_gray_glacier_header_from_parent(
    difficulty_fn: Callable[[BlockHeaderAPI, int], int],
    parent_header: Optional[BlockHeaderAPI],
    **header_params: Any,
) -> BlockHeaderAPI:
    arrow_glacier_validated_header = create_arrow_glacier_header_from_parent(
        difficulty_fn, parent_header, **header_params
    )

    # extract header params validated up to arrow glacier (previous VM) and plug
    # into `GrayGlacierBlockHeader` class
    all_fields = arrow_glacier_validated_header.as_dict()
    return GrayGlacierBlockHeader(**all_fields)
