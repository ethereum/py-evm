from evm.vm.shard_vm import (
    ShardVM,
)
from evm.vm.forks.byzantium import (
    configure_byzantium_header,
    compute_byzantium_difficulty,
)

from .collations import Collation
from .headers import (
    create_sharding_header_from_parent,
)
from .vm_state import ShardingVMState

ShardingVM = ShardVM.configure(
    __name__='ShardingVM',
    # classes
    _block_class=Collation,
    _state_class=ShardingVMState,
    # TODO: Replace them after we apply Collation structure
    create_header_from_parent=staticmethod(create_sharding_header_from_parent),
    compute_difficulty=staticmethod(compute_byzantium_difficulty),
    configure_header=configure_byzantium_header,
)
