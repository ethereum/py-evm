from eth.vm.forks.london.blocks import LondonBlockHeader
from eth.constants import GENESIS_GAS_LIMIT
from eth._utils.headers import compute_gas_limit
from eth.abc import BlockHeaderAPI
from typing import Any, Callable
from toolz.functoolz import curry
from eth.vm.forks.berlin.headers import (
    configure_header,
    compute_berlin_difficulty,
)

@curry
def create_header_from_parent(difficulty_fn: Callable[[BlockHeaderAPI, int], int],
                              parent_header: BlockHeaderAPI,
                              **header_params: Any) -> BlockHeaderAPI:
    # byzantium
    if 'difficulty' not in header_params:
        header_params.setdefault('timestamp', parent_header.timestamp + 1)

        header_params['difficulty'] = difficulty_fn(
            parent_header,
            header_params['timestamp'],
        )

    # frontier
    if 'gas_limit' not in header_params:
        header_params['gas_limit'] = compute_gas_limit(
            parent_header,
            gas_limit_floor=GENESIS_GAS_LIMIT,
        )

    header = LondonBlockHeader.from_parent(parent=parent_header, **header_params)
    return header


compute_london_difficulty = compute_berlin_difficulty

create_london_header_from_parent = create_header_from_parent(
    compute_london_difficulty
)

# TODO update configure_header
# configure_london_header = configure_header(compute_berlin_difficulty)
