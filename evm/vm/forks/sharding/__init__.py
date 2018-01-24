from evm.vm.forks.byzantium import ByzantiumVM

from .blocks import ShardingBlock
from .vm_state import ShardingVMState


ShardingVM = ByzantiumVM.configure(
    name='ShardingVM',
    # classes
    _block_class=ShardingBlock,
    _state_class=ShardingVMState,
)
