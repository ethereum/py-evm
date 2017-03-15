import logging

from toolz import (
    partial,
)

from evm.gas import (
    COST_VERYLOW,
)


logger = logging.getLogger('evm.logic.swap')


def swap_XX(message, storage, state, position):
    """
    Addition
    """
    state.stack.swap(position)
    logger.info('SWAP%s')
    state.consume_gas(COST_VERYLOW)


swap1 = partial(swap_XX, position=1)
swap2 = partial(swap_XX, position=2)
swap3 = partial(swap_XX, position=3)
swap4 = partial(swap_XX, position=4)
swap5 = partial(swap_XX, position=5)
swap6 = partial(swap_XX, position=6)
swap7 = partial(swap_XX, position=7)
swap8 = partial(swap_XX, position=8)
swap9 = partial(swap_XX, position=9)
swap10 = partial(swap_XX, position=10)
swap11 = partial(swap_XX, position=11)
swap12 = partial(swap_XX, position=12)
swap13 = partial(swap_XX, position=13)
swap14 = partial(swap_XX, position=14)
swap15 = partial(swap_XX, position=15)
swap16 = partial(swap_XX, position=16)
