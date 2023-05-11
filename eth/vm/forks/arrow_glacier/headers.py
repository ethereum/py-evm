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
from eth.vm.forks.byzantium.headers import (
    compute_difficulty,
    configure_header,
)
from eth.vm.forks.london.headers import (
    create_london_header_from_parent,
)

from .blocks import (
    ArrowGlacierBlockHeader,
)

compute_arrow_glacier_difficulty = compute_difficulty(10_700_000)
configure_arrow_glacier_header = configure_header(
    difficulty_fn=compute_arrow_glacier_difficulty
)


@curry
def create_arrow_glacier_header_from_parent(
    difficulty_fn: Callable[[BlockHeaderAPI, int], int],
    parent_header: Optional[BlockHeaderAPI],
    **header_params: Any,
) -> BlockHeaderAPI:
    london_validated_header = create_london_header_from_parent(
        difficulty_fn, parent_header, **header_params
    )

    # extract header params validated up to london (previous VM) and plug
    # into `ArrowGlacierBlockHeader` class
    all_fields = london_validated_header.as_dict()
    return ArrowGlacierBlockHeader(**all_fields)
