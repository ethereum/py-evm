from __future__ import absolute_import

from evm import VM
from evm.constants import (
    BLOCK_REWARD,
    UNCLE_DEPTH_PENALTY_FACTOR,
)

from .blocks import FrontierBlock
from .vm_state import FrontierVMState
from .headers import (
    create_frontier_header_from_parent,
    compute_frontier_difficulty,
    configure_frontier_header,
)


def _frontier_get_block_reward():
    return BLOCK_REWARD


def _frontier_get_uncle_reward(block_number, uncle):
    return BLOCK_REWARD * (
        UNCLE_DEPTH_PENALTY_FACTOR + uncle.block_number - block_number
    ) // UNCLE_DEPTH_PENALTY_FACTOR


def _frontier_get_nephew_reward(cls):
    return cls.get_block_reward() // 32


FrontierVM = VM.configure(
    name='FrontierVM',
    # classes
    _block_class=FrontierBlock,
    _state_class=FrontierVMState,
    # helpers
    create_header_from_parent=staticmethod(create_frontier_header_from_parent),
    compute_difficulty=staticmethod(compute_frontier_difficulty),
    configure_header=configure_frontier_header,
    get_block_reward=staticmethod(_frontier_get_block_reward),
    get_uncle_reward=staticmethod(_frontier_get_uncle_reward),
    get_nephew_reward=_frontier_get_nephew_reward,
    # mode
    _is_stateless=True,
)
