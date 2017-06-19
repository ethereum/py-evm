from __future__ import absolute_import

from evm.validation import (
    validate_gt,
)
from evm.constants import (
    DIFFICULTY_ADJUSTMENT_DENOMINATOR,
    DIFFICULTY_MINIMUM,
    BOMB_EXPONENTIAL_PERIOD,
    BOMB_EXPONENTIAL_FREE_PERIODS,
    FRONTIER_DIFFICULTY_ADJUSTMENT_CUTOFF,
)


def compute_frontier_difficulty(parent_header, timestamp):
    """
    Computes the difficulty for a frontier block based on the parent block.
    """
    validate_gt(timestamp, parent_header.timestamp)

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


ALLOWED_HEADER_FIELDS = {
    'coinbase',
    'gas_limit',
    'timestamp',
    'extra_data',
    'mix_hash',
    'nonce',
}


def setup_header(evm, **header_params):
    extra_fields = set(header_params.keys()).difference(ALLOWED_HEADER_FIELDS)
    if extra_fields:
        raise ValueError(
            "The `setup_header` method may only be used with the fields ({0}). "
            "The provided fields ({1}) are not supported".format(
                ", ".join(tuple(sorted(ALLOWED_HEADER_FIELDS))),
                ", ".join(tuple(sorted(extra_fields))),
            )
        )

    for field_name, value in header_params.items():
        setattr(evm.header, field_name, value)

    if 'timestamp' in header_params and evm.header.block_number > 0:
        parent_header = evm.block.get_parent_header()
        evm.header.difficulty = evm.compute_difficulty(
            parent_header,
            header_params['timestamp'],
        )

    return evm.header
