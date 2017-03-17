class BaseEVMError(Exception):
    pass


class EmptyStream(BaseEVMError):
    pass


class VMError(BaseEVMError):
    pass


class OutOfGas(VMError):
    pass


class InsufficientStack(VMError):
    pass


class FullStack(VMError):
    pass


class InvalidJumpDestination(VMError):
    pass


class InvalidInstruction(VMError):
    pass
