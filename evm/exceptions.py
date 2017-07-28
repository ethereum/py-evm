class PyEVMError(Exception):
    """
    Base error class for all py-evm errors.
    """
    pass


class VMNotFound(PyEVMError):
    """
    No VM available for the provided block number.
    """
    pass


class BlockNotFound(PyEVMError):
    """
    The block with the given number/hash does not exist.
    """
    pass


class ValidationError(PyEVMError):
    """
    Error to signal something does not pass a validation check.
    """
    pass


class VMError(PyEVMError):
    """
    Class of errors which can be raised during VM execution.
    """
    pass


class OutOfGas(VMError):
    """
    Error signaling that VM execution has run out of gas.
    """
    pass


class InsufficientStack(VMError):
    """
    Error signaling that the stack is empty.
    """
    pass


class FullStack(VMError):
    """
    Error signaling that the stack is full.
    """
    pass


class InvalidJumpDestination(VMError):
    """
    Error signaling that the jump destination for a JUMPDEST operation is invalid.
    """
    pass


class InvalidInstruction(VMError):
    """
    Error signaling that an opcode is invalid.
    """
    pass


class InsufficientFunds(VMError):
    """
    Error signaling that an account has insufficient funds to transfer the
    requested value.
    """
    pass


class StackDepthLimit(VMError):
    """
    Error signaling that the call stack has exceeded it's maximum allowed depth.
    """
    pass
