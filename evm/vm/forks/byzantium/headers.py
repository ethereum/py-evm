from evm.constants import (
    EMPTY_UNCLE_HASH,
    DIFFICULTY_ADJUSTMENT_DENOMINATOR,
    DIFFICULTY_MINIMUM,
    BOMB_EXPONENTIAL_PERIOD,
    BOMB_EXPONENTIAL_FREE_PERIODS,
)
from evm.utils.db import (
    get_parent_header,
)
from evm.validation import (
    validate_gt,
    validate_header_params_for_configuration,
)
from evm.vm.forks.frontier.headers import (
    create_frontier_header_from_parent,
)

from .constants import (
    BYZANTIUM_DIFFICULTY_ADJUSTMENT_CUTOFF
)


def compute_byzantium_difficulty(parent_header, timestamp):
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
            parent_header.block_number + 1 - 3000000,
        ) // BOMB_EXPONENTIAL_PERIOD
    ) - BOMB_EXPONENTIAL_FREE_PERIODS

    if num_bomb_periods >= 0:
        return max(difficulty + 2**num_bomb_periods, DIFFICULTY_MINIMUM)
    else:
        return difficulty


def create_byzantium_header_from_parent(parent_header, **header_params):
    if 'difficulty' not in header_params:
        header_params.setdefault('timestamp', parent_header.timestamp + 1)

        header_params['difficulty'] = compute_byzantium_difficulty(
            parent_header=parent_header,
            timestamp=header_params['timestamp'],
        )
    return create_frontier_header_from_parent(parent_header, **header_params)


def configure_byzantium_header(vm, **header_params):
    validate_header_params_for_configuration(header_params)

    for field_name, value in header_params.items():
        setattr(vm.block.header, field_name, value)

    if 'timestamp' in header_params and vm.block.header.block_number > 0:
        parent_header = get_parent_header(vm.block.header, vm.chaindb)
        vm.block.header.difficulty = compute_byzantium_difficulty(
            parent_header,
            header_params['timestamp'],
        )

    return vm.block.header
