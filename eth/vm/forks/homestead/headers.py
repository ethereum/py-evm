from typing import (
    Any,
    TYPE_CHECKING,
)

from eth_typing import (
    Address,
)
from eth_utils import (
    decode_hex,
)

from eth.constants import (
    DIFFICULTY_ADJUSTMENT_DENOMINATOR,
    DIFFICULTY_MINIMUM,
    BOMB_EXPONENTIAL_PERIOD,
    BOMB_EXPONENTIAL_FREE_PERIODS,
)
from eth.rlp.headers import BlockHeader
from eth._utils.db import (
    get_parent_header,
)
from eth.validation import (
    validate_gt,
    validate_header_params_for_configuration,
)
from eth.vm.forks.frontier.headers import (
    create_frontier_header_from_parent,
)

from .constants import (
    HOMESTEAD_DIFFICULTY_ADJUSTMENT_CUTOFF
)

if TYPE_CHECKING:
    from eth.vm.forks.homestead import HomesteadVM      # noqa: F401


def compute_homestead_difficulty(parent_header: BlockHeader, timestamp: int) -> int:
    """
    Computes the difficulty for a homestead block based on the parent block.
    """
    parent_tstamp = parent_header.timestamp
    validate_gt(timestamp, parent_tstamp, title="Header.timestamp")
    offset = parent_header.difficulty // DIFFICULTY_ADJUSTMENT_DENOMINATOR
    sign = max(
        1 - (timestamp - parent_tstamp) // HOMESTEAD_DIFFICULTY_ADJUSTMENT_CUTOFF,
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


def create_homestead_header_from_parent(parent_header: BlockHeader,
                                        **header_params: Any) -> BlockHeader:
    if 'difficulty' not in header_params:
        # Use setdefault to ensure the new header has the same timestamp we use to calculate its
        # difficulty.
        header_params.setdefault('timestamp', parent_header.timestamp + 1)
        header_params['difficulty'] = compute_homestead_difficulty(
            parent_header,
            header_params['timestamp'],
        )
    return create_frontier_header_from_parent(parent_header, **header_params)


def configure_homestead_header(vm: "HomesteadVM", **header_params: Any) -> BlockHeader:
    validate_header_params_for_configuration(header_params)

    with vm.get_header().build_changeset(**header_params) as changeset:
        if 'timestamp' in header_params and changeset.block_number > 0:
            parent_header = get_parent_header(changeset.build_rlp(), vm.chaindb)
            changeset.difficulty = compute_homestead_difficulty(
                parent_header,
                header_params['timestamp'],
            )

        header = changeset.commit()
    return header
