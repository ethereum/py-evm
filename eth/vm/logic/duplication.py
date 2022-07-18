import functools

from eth.abc import (
    ComputationAPI,
)


def dup_XX(computation: ComputationAPI, position: int) -> None:
    """
    Stack item duplication.
    """
    computation.stack_dup(position)

def dup1(computation):
    dup_XX(computation, 1)
def dup2(computation):
    dup_XX(computation, 2)
def dup3(computation):
    dup_XX(computation, 3)
def dup4(computation):
    dup_XX(computation, 4)
def dup5(computation):
    dup_XX(computation, 5)
def dup6(computation):
    dup_XX(computation, 6)
def dup7(computation):
    dup_XX(computation, 7)
def dup8(computation):
    dup_XX(computation, 8)
def dup9(computation):
    dup_XX(computation, 9)
def dup10(computation):
    dup_XX(computation, 10)
def dup11(computation):
    dup_XX(computation, 11)
def dup12(computation):
    dup_XX(computation, 12)
def dup13(computation):
    dup_XX(computation, 13)
def dup14(computation):
    dup_XX(computation, 14)
def dup15(computation):
    dup_XX(computation, 15)
def dup16(computation):
    dup_XX(computation, 16)
