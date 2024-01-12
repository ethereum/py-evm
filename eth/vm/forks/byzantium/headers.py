from typing import (
    Any,
    Callable,
    Optional,
)

from eth_utils.toolz import (
    curry,
)

from eth._utils.db import (
    get_parent_header,
)
from eth._utils.headers import (
    new_timestamp_from_parent,
)
from eth.abc import (
    BlockHeaderAPI,
    VirtualMachineAPI,
)
from eth.constants import (
    BOMB_EXPONENTIAL_FREE_PERIODS,
    BOMB_EXPONENTIAL_PERIOD,
    DIFFICULTY_ADJUSTMENT_DENOMINATOR,
    DIFFICULTY_MINIMUM,
    EMPTY_UNCLE_HASH,
)
from eth.validation import (
    validate_gt,
    validate_header_params_for_configuration,
)
from eth.vm.forks.frontier.headers import (
    create_frontier_header_from_parent,
)

from .constants import (
    BYZANTIUM_DIFFICULTY_ADJUSTMENT_CUTOFF,
)


@curry
def compute_difficulty(
    bomb_delay: int, parent_header: BlockHeaderAPI, timestamp: int
) -> int:
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
            (2 if has_uncles else 1)
            - ((timestamp - parent_timestamp) // BYZANTIUM_DIFFICULTY_ADJUSTMENT_CUTOFF)
        ),
        -99,
    )
    difficulty = max(parent_difficulty + offset * adj_factor, DIFFICULTY_MINIMUM)
    num_bomb_periods = (
        max(
            0,
            parent_header.block_number + 1 - bomb_delay,
        )
        // BOMB_EXPONENTIAL_PERIOD
    ) - BOMB_EXPONENTIAL_FREE_PERIODS

    if num_bomb_periods >= 0:
        return max(difficulty + 2**num_bomb_periods, DIFFICULTY_MINIMUM)
    else:
        return difficulty


@curry
def create_header_from_parent(
    difficulty_fn: Callable[[BlockHeaderAPI, int], int],
    parent_header: BlockHeaderAPI,
    **header_params: Any,
) -> BlockHeaderAPI:
    if "timestamp" not in header_params:
        header_params["timestamp"] = new_timestamp_from_parent(parent_header)

    if "difficulty" not in header_params:
        header_params["difficulty"] = difficulty_fn(
            parent_header,
            header_params["timestamp"],
        )
    return create_frontier_header_from_parent(parent_header, **header_params)


@curry
def configure_header(
    vm: VirtualMachineAPI,
    difficulty_fn: Optional[Callable[[BlockHeaderAPI, int], int]] = None,
    **header_params: Any,
) -> BlockHeaderAPI:
    validate_header_params_for_configuration(header_params)

    with vm.get_header().build_changeset(**header_params) as changeset:
        if (
            "timestamp" in header_params
            and changeset.block_number > 0
            # post-POS does not use difficulty_fn
            and difficulty_fn is not None
        ):
            parent_header = get_parent_header(changeset.build_rlp(), vm.chaindb)
            changeset.difficulty = difficulty_fn(
                parent_header,
                header_params["timestamp"],
            )

        header = changeset.commit()
    return header


compute_byzantium_difficulty = compute_difficulty(3000000)
create_byzantium_header_from_parent = create_header_from_parent(
    compute_byzantium_difficulty
)
configure_byzantium_header = configure_header(
    difficulty_fn=compute_byzantium_difficulty
)
