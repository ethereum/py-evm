from __future__ import absolute_import

from evm import VM
from .blocks import FrontierBlock
from .computation import FrontierComputation
from .vm_state import FrontierVMState
from .validation import validate_frontier_transaction
from .headers import (
    create_frontier_header_from_parent,
    configure_frontier_header,
)


FrontierVM = VM.configure(
    name='FrontierVM',
    # classes
    _block_class=FrontierBlock,
    _computation_class=FrontierComputation,
    _state_class=FrontierVMState,
    # helpers
    create_header_from_parent=staticmethod(create_frontier_header_from_parent),
    configure_header=configure_frontier_header,
    # validation
    validate_transaction=validate_frontier_transaction,
)
