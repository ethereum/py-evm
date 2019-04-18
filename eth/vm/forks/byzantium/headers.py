from typing import (
    Any,
    Callable,
)
from eth_utils.toolz import (
    curry,
)
from eth.constants import (
    EMPTY_UNCLE_HASH,
    DIFFICULTY_ADJUSTMENT_DENOMINATOR,
    DIFFICULTY_MINIMUM,
    BOMB_EXPONENTIAL_PERIOD,
    BOMB_EXPONENTIAL_FREE_PERIODS,
)
from eth.rlp.headers import (
    BlockHeader,
)
from eth._utils.db import (
    get_parent_header,
)
from eth.validation import (
    validate_gt,
    validate_header_params_for_configuration,
)
from eth.vm.base import (
    BaseVM
)
from eth.vm.forks.frontier.headers import (
    create_frontier_header_from_parent,
)

from .constants import (
    BYZANTIUM_DIFFICULTY_ADJUSTMENT_CUTOFF
)


@curry
def compute_difficulty(
        bomb_delay: int,
        parent_header: BlockHeader,
        timestamp: int) -> int:
    """
    https://github.com/ethereum/EIPs/issues/100
    """
    parent_timestamp = parent_header.timestamp
    validate_gt(timestamp, parent_timestamp, title="Header.timestamp")

    parent_difficulty = parent_header.difficulty
    offset = parent_difficulty // DIFFICULTY_ADJUSTMENT_DENOMINATOR

    has_uncles = parent_header.uncles_hash != EMPTY_UNCLE_HASH
    adj_factor = max(
        (
            (2 if has_uncles else 1) -
            ((timestamp - parent_timestamp) // BYZANTIUM_DIFFICULTY_ADJUSTMENT_CUTOFF)
        ),
        -99,
    )
    difficulty = max(
        parent_difficulty + offset * adj_factor,
        min(parent_header.difficulty, DIFFICULTY_MINIMUM)
    )
    num_bomb_periods = (
        max(
            0,
            parent_header.block_number + 1 - bomb_delay,
        ) // BOMB_EXPONENTIAL_PERIOD
    ) - BOMB_EXPONENTIAL_FREE_PERIODS

    if num_bomb_periods >= 0:
        return max(difficulty + 2**num_bomb_periods, DIFFICULTY_MINIMUM)
    else:
        return difficulty


@curry
def create_header_from_parent(difficulty_fn: Callable[[BlockHeader, int], int],
                              parent_header: BlockHeader,
                              **header_params: Any) -> BlockHeader:

    if 'difficulty' not in header_params:
        header_params.setdefault('timestamp', parent_header.timestamp + 1)

        header_params['difficulty'] = difficulty_fn(
            parent_header,
            header_params['timestamp'],
        )
    return create_frontier_header_from_parent(parent_header, **header_params)


@curry
def configure_header(difficulty_fn: Callable[[BlockHeader, int], int],
                     vm: BaseVM,
                     **header_params: Any) -> BlockHeader:
    validate_header_params_for_configuration(header_params)

    with vm.header.build_changeset(**header_params) as changeset:
        if 'timestamp' in header_params and changeset.block_number > 0:
            parent_header = get_parent_header(changeset.build_rlp(), vm.chaindb)
            changeset.difficulty = difficulty_fn(
                parent_header,
                header_params['timestamp'],
            )

        header = changeset.commit()
    return header


compute_byzantium_difficulty = compute_difficulty(3000000)
create_byzantium_header_from_parent = create_header_from_parent(compute_byzantium_difficulty)
configure_byzantium_header = configure_header(compute_byzantium_difficulty)
