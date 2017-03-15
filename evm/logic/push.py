import logging

from toolz import (
    partial,
)

from evm.gas import (
    COST_VERYLOW,
)


logger = logging.getLogger('evm.logic.push.push')


def push_XX(message, state, storage, size):
    value_to_push = state.code.read(size)
    logger.info('PUSH%s: %s', size, value_to_push)
    state.stack.push(value_to_push)

    state.consume_gas(COST_VERYLOW)


push_1 = partial(push_XX, size=1)
push_2 = partial(push_XX, size=2)
push_3 = partial(push_XX, size=3)
push_4 = partial(push_XX, size=4)
push_5 = partial(push_XX, size=5)
push_6 = partial(push_XX, size=6)
push_7 = partial(push_XX, size=7)
push_8 = partial(push_XX, size=8)
push_9 = partial(push_XX, size=9)
push_10 = partial(push_XX, size=10)
push_11 = partial(push_XX, size=11)
push_12 = partial(push_XX, size=12)
push_13 = partial(push_XX, size=13)
push_14 = partial(push_XX, size=14)
push_15 = partial(push_XX, size=15)
push_16 = partial(push_XX, size=16)
push_17 = partial(push_XX, size=17)
push_18 = partial(push_XX, size=18)
push_19 = partial(push_XX, size=19)
push_20 = partial(push_XX, size=20)
push_21 = partial(push_XX, size=21)
push_22 = partial(push_XX, size=22)
push_23 = partial(push_XX, size=23)
push_24 = partial(push_XX, size=24)
push_25 = partial(push_XX, size=25)
push_26 = partial(push_XX, size=26)
push_27 = partial(push_XX, size=27)
push_28 = partial(push_XX, size=28)
push_29 = partial(push_XX, size=29)
push_30 = partial(push_XX, size=30)
push_31 = partial(push_XX, size=31)
push_32 = partial(push_XX, size=32)
