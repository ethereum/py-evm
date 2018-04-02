from __future__ import absolute_import

from evm.vm import VM

from .state import FrontierState
from .headers import (
    create_frontier_header_from_parent,
    compute_frontier_difficulty,
    configure_frontier_header,
)


FrontierVM = VM.configure(
    # class name
    __name__='FrontierVM',
    # fork name
    fork='frontier',
    # classes
    _state_class=FrontierState,
    # helpers
    create_header_from_parent=staticmethod(create_frontier_header_from_parent),
    compute_difficulty=staticmethod(compute_frontier_difficulty),
    configure_header=configure_frontier_header,
)
