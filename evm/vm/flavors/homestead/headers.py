from evm.validation import (
    validate_gt,
)
from evm.constants import (
    DIFFICULTY_ADJUSTMENT_DENOMINATOR,
    DIFFICULTY_MINIMUM,
    BOMB_EXPONENTIAL_PERIOD,
    BOMB_EXPONENTIAL_FREE_PERIODS,
    HOMESTEAD_DIFF_ADJUSTMENT_CUTOFF,
)

from evm.vm.flavors.frontier.headers import (
    configure_frontier_header,
    create_frontier_header_from_parent,
)


def compute_homestead_difficulty(parent_header, timestamp):
    """
    Computes the difficulty for a homestead block based on the parent block.
    """
    parent_tstamp = parent_header.timestamp
    validate_gt(timestamp, parent_tstamp)
    offset = parent_header.difficulty // DIFFICULTY_ADJUSTMENT_DENOMINATOR
    sign = max(
        1 - (timestamp - parent_tstamp) // HOMESTEAD_DIFF_ADJUSTMENT_CUTOFF,
        -99)
    difficulty = int(max(
        parent_header.difficulty + offset * sign,
        min(parent_header.difficulty, DIFFICULTY_MINIMUM)))
    num_bomb_periods = (
        (parent_header.block_number + 1) // BOMB_EXPONENTIAL_PERIOD
    ) - BOMB_EXPONENTIAL_FREE_PERIODS
    if num_bomb_periods >= 0:
        return max(difficulty + 2**num_bomb_periods, DIFFICULTY_MINIMUM)
    else:
        return difficulty


def create_homestead_header_from_parent(parent_header, **header_params):
    if 'difficulty' not in header_params:
        timestamp = header_params.get('timestamp', parent_header.timestamp + 1)
        header_params['difficulty'] = compute_homestead_difficulty(
            parent_header,
            timestamp,
        )
    return create_frontier_header_from_parent(parent_header, **header_params)


def configure_homestead_header(vm, **header_params):
    header = configure_frontier_header(vm, **header_params)
    if 'timestamp' in header_params and header.block_number > 0:
        parent_header = vm.block.get_parent_header()
        header.difficulty = compute_homestead_difficulty(
            parent_header,
            header_params['timestamp'],
        )
    return header
