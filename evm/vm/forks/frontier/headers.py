from __future__ import absolute_import

from evm.validation import (
    validate_gt,
    validate_header_params_for_configuration,
)

from evm.constants import (
    GENESIS_GAS_LIMIT,
    DIFFICULTY_ADJUSTMENT_DENOMINATOR,
    DIFFICULTY_MINIMUM,
    BOMB_EXPONENTIAL_PERIOD,
    BOMB_EXPONENTIAL_FREE_PERIODS,
)
from evm.utils.db import (
    get_parent_header,
)
from evm.utils.headers import (
    compute_gas_limit,
)
from evm.rlp.headers import BlockHeader

from .constants import (
    FRONTIER_DIFFICULTY_ADJUSTMENT_CUTOFF
)


def compute_frontier_difficulty(parent_header, timestamp):
    """
    Computes the difficulty for a frontier block based on the parent block.
    """
    validate_gt(timestamp, parent_header.timestamp, title="Header timestamp")

    offset = parent_header.difficulty // DIFFICULTY_ADJUSTMENT_DENOMINATOR

    # We set the minimum to the lowest of the protocol minimum and the parent
    # minimum to allow for the initial frontier *warming* period during which
    # the difficulty begins lower than the protocol minimum.
    difficulty_minimum = min(parent_header.difficulty, DIFFICULTY_MINIMUM)

    if timestamp - parent_header.timestamp < FRONTIER_DIFFICULTY_ADJUSTMENT_CUTOFF:
        base_difficulty = max(
            parent_header.difficulty + offset,
            difficulty_minimum,
        )
    else:
        base_difficulty = max(
            parent_header.difficulty - offset,
            difficulty_minimum,
        )

    # Adjust for difficulty bomb.
    num_bomb_periods = (
        (parent_header.block_number + 1) // BOMB_EXPONENTIAL_PERIOD
    ) - BOMB_EXPONENTIAL_FREE_PERIODS

    if num_bomb_periods >= 0:
        difficulty = max(
            base_difficulty + 2**num_bomb_periods,
            DIFFICULTY_MINIMUM,
        )
    else:
        difficulty = base_difficulty

    return difficulty


def create_frontier_header_from_parent(parent_header, **header_params):
    if 'difficulty' not in header_params:
        # Use setdefault to ensure the new header has the same timestamp we use to calculate its
        # difficulty.
        header_params.setdefault('timestamp', parent_header.timestamp + 1)
        header_params['difficulty'] = compute_frontier_difficulty(
            parent_header,
            header_params['timestamp'],
        )
    if 'gas_limit' not in header_params:
        header_params['gas_limit'] = compute_gas_limit(
            parent_header,
            gas_limit_floor=GENESIS_GAS_LIMIT,
        )

    header = BlockHeader.from_parent(parent=parent_header, **header_params)

    return header


def configure_frontier_header(vm, **header_params):
    validate_header_params_for_configuration(header_params)

    for field_name, value in header_params.items():
        setattr(vm.block.header, field_name, value)

    if 'timestamp' in header_params and vm.block.header.block_number > 0:
        parent_header = get_parent_header(vm.block.header, vm.chaindb)
        vm.block.header.difficulty = compute_frontier_difficulty(
            parent_header,
            header_params['timestamp'],
        )

    return vm.block.header
