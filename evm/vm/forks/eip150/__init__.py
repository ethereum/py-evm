from ..homestead import HomesteadVM

from .opcodes import EIP150_OPCODES


EIP150VM = HomesteadVM.configure(
    name='EIP150',
    opcodes=EIP150_OPCODES,
)
