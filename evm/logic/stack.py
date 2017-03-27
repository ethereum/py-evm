import logging

from toolz import (
    partial,
)

from evm.utils.numeric import (
    big_endian_to_int,
)
from evm.utils.padding import (
    pad_right,
)


logger = logging.getLogger('evm.logic.memory')


def pop(computation):
    logger.info('POP: %s', computation.stack.pop())


def push_XX(computation, size):
    raw_value = computation.code.read(size)

    if not raw_value.strip(b'\x00'):
        logger.info('PUSH%s: %s', size, b'\x00' * size)
        computation.stack.push(0)
    else:
        padded_value = pad_right(raw_value, size, b'\x00')
        logger.info('PUSH%s: %s', size, padded_value)
        computation.stack.push(padded_value)


push1 = partial(push_XX, size=1)
push2 = partial(push_XX, size=2)
push3 = partial(push_XX, size=3)
push4 = partial(push_XX, size=4)
push5 = partial(push_XX, size=5)
push6 = partial(push_XX, size=6)
push7 = partial(push_XX, size=7)
push8 = partial(push_XX, size=8)
push9 = partial(push_XX, size=9)
push10 = partial(push_XX, size=10)
push11 = partial(push_XX, size=11)
push12 = partial(push_XX, size=12)
push13 = partial(push_XX, size=13)
push14 = partial(push_XX, size=14)
push15 = partial(push_XX, size=15)
push16 = partial(push_XX, size=16)
push17 = partial(push_XX, size=17)
push18 = partial(push_XX, size=18)
push19 = partial(push_XX, size=19)
push20 = partial(push_XX, size=20)
push21 = partial(push_XX, size=21)
push22 = partial(push_XX, size=22)
push23 = partial(push_XX, size=23)
push24 = partial(push_XX, size=24)
push25 = partial(push_XX, size=25)
push26 = partial(push_XX, size=26)
push27 = partial(push_XX, size=27)
push28 = partial(push_XX, size=28)
push29 = partial(push_XX, size=29)
push30 = partial(push_XX, size=30)
push31 = partial(push_XX, size=31)
push32 = partial(push_XX, size=32)
