import logging

from toolz import (
    partial,
)


logger = logging.getLogger('evm.logic.dup')


def dup_XX(computation, position):
    """
    Stack item duplication.
    """
    computation.stack.dup(position)
    logger.info('DUP%s')


dup1 = partial(dup_XX, position=1)
dup2 = partial(dup_XX, position=2)
dup3 = partial(dup_XX, position=3)
dup4 = partial(dup_XX, position=4)
dup5 = partial(dup_XX, position=5)
dup6 = partial(dup_XX, position=6)
dup7 = partial(dup_XX, position=7)
dup8 = partial(dup_XX, position=8)
dup9 = partial(dup_XX, position=9)
dup10 = partial(dup_XX, position=10)
dup11 = partial(dup_XX, position=11)
dup12 = partial(dup_XX, position=12)
dup13 = partial(dup_XX, position=13)
dup14 = partial(dup_XX, position=14)
dup15 = partial(dup_XX, position=15)
dup16 = partial(dup_XX, position=16)
