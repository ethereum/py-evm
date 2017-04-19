class BaseEVMError(Exception):
    """
    Base error class for all py-evm errors.
    """
    pass


class ValidationError(BaseEVMError):
    """
    Error to signal something does not pass a validation check.
    """
    pass


class VMError(BaseEVMError):
    """
    Class of errors which can be raised during EVM execution.
    """
    pass


class OutOfGas(VMError):
    """
    Error signaling that EVM execution has run out of gas.
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


class InvalidTransaction(BaseEVMError):
    """
    Error for signaling a transaction is invalid.
    """
    pass


class EVMNotFound(BaseEVMError):
    """
    Error for when there is no defined EVM for a given block number.
    """
    pass
