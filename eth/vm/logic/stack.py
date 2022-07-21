from eth.abc import (
    ComputationAPI,
)


def pop(computation: ComputationAPI) -> None:
    computation.stack_pop1_any()


def push_XX(computation: ComputationAPI, size: int) -> None:
    raw_value = computation.code.read(size)

    # This is a performance-sensitive area.
    # Calling raw_value.ljust() when size == len(raw_value) is more expensive than
    # calling len(raw_value) and raw_len is typically the correct size already,
    # so this saves a bit of time:
    raw_len = len(raw_value)
    if raw_len == size:
        computation.stack_push_bytes(raw_value)
    else:
        padded_value = raw_value.ljust(size, b"\x00")
        computation.stack_push_bytes(padded_value)


def push0(computation: ComputationAPI) -> None:
    return push_XX(computation, 0)


def push1(computation: ComputationAPI) -> None:
    return push_XX(computation, 1)


def push2(computation: ComputationAPI) -> None:
    return push_XX(computation, 2)


def push3(computation: ComputationAPI) -> None:
    return push_XX(computation, 3)


def push4(computation: ComputationAPI) -> None:
    return push_XX(computation, 4)


def push5(computation: ComputationAPI) -> None:
    return push_XX(computation, 5)


def push6(computation: ComputationAPI) -> None:
    return push_XX(computation, 6)


def push7(computation: ComputationAPI) -> None:
    return push_XX(computation, 7)


def push8(computation: ComputationAPI) -> None:
    return push_XX(computation, 8)


def push9(computation: ComputationAPI) -> None:
    return push_XX(computation, 9)


def push10(computation: ComputationAPI) -> None:
    return push_XX(computation, 10)


def push11(computation: ComputationAPI) -> None:
    return push_XX(computation, 11)


def push12(computation: ComputationAPI) -> None:
    return push_XX(computation, 12)


def push13(computation: ComputationAPI) -> None:
    return push_XX(computation, 13)


def push14(computation: ComputationAPI) -> None:
    return push_XX(computation, 14)


def push15(computation: ComputationAPI) -> None:
    return push_XX(computation, 15)


def push16(computation: ComputationAPI) -> None:
    return push_XX(computation, 16)


def push17(computation: ComputationAPI) -> None:
    return push_XX(computation, 17)


def push18(computation: ComputationAPI) -> None:
    return push_XX(computation, 18)


def push19(computation: ComputationAPI) -> None:
    return push_XX(computation, 19)


def push20(computation: ComputationAPI) -> None:
    return push_XX(computation, 20)


def push21(computation: ComputationAPI) -> None:
    return push_XX(computation, 21)


def push22(computation: ComputationAPI) -> None:
    return push_XX(computation, 22)


def push23(computation: ComputationAPI) -> None:
    return push_XX(computation, 23)


def push24(computation: ComputationAPI) -> None:
    return push_XX(computation, 24)


def push25(computation: ComputationAPI) -> None:
    return push_XX(computation, 25)


def push26(computation: ComputationAPI) -> None:
    return push_XX(computation, 26)


def push27(computation: ComputationAPI) -> None:
    return push_XX(computation, 27)


def push28(computation: ComputationAPI) -> None:
    return push_XX(computation, 28)


def push29(computation: ComputationAPI) -> None:
    return push_XX(computation, 29)


def push30(computation: ComputationAPI) -> None:
    return push_XX(computation, 30)


def push31(computation: ComputationAPI) -> None:
    return push_XX(computation, 31)


def push32(computation: ComputationAPI) -> None:
    return push_XX(computation, 32)
