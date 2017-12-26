from ..homestead import HomesteadVM

from .opcodes import TANGERINE_WHISTLE_OPCODES


TangerineWhistleVM = HomesteadVM.configure(
    name='TangerineWhistleVM',
    opcodes=TANGERINE_WHISTLE_OPCODES,
)
