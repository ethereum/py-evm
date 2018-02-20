from __future__ import absolute_import

from evm import VM

from .blocks import FrontierBlock
from .vm_state import FrontierVMState
from .headers import (
    create_frontier_header_from_parent,
    compute_frontier_difficulty,
    configure_frontier_header,
)


FrontierVM = VM.configure(
    __name__='FrontierVM',
    # classes
    _block_class=FrontierBlock,
    _state_class=FrontierVMState,
    # helpers
    create_header_from_parent=staticmethod(create_frontier_header_from_parent),
    compute_difficulty=staticmethod(compute_frontier_difficulty),
    configure_header=configure_frontier_header,
)
