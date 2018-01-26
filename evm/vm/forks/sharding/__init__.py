from evm.vm.shard_vm import (
    ShardVM,
)
from evm.vm.forks.byzantium import (
    create_byzantium_header_from_parent,
    configure_byzantium_header,
    compute_byzantium_difficulty,
)

from .blocks import ShardingBlock
from .vm_state import ShardingVMState


ShardingVM = ShardVM.configure(
    name='ShardingVM',
    # classes
    _block_class=ShardingBlock,
    _state_class=ShardingVMState,
    # TODO: Replace them after we apply Collation structure
    create_header_from_parent=staticmethod(create_byzantium_header_from_parent),
    compute_difficulty=staticmethod(compute_byzantium_difficulty),
    configure_header=configure_byzantium_header,
)
