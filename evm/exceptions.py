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


class TransactionNotFound(PyEVMError):
    """
    The transaction with the given hash or block index dos not exist.
    """
    pass


class ParentNotFound(PyEVMError):
    """
    The parent of a given block does not exist.
    """
    pass


class CanonicalHeadNotFound(PyEVMError):
    """
    The chain has no canonical head.
    """
    pass


class ValidationError(PyEVMError):
    """
    Error to signal something does not pass a validation check.
    """
    pass


class Halt(PyEVMError):
    """
    Raised by opcode function to halt vm execution.
    """
    pass


class VMError(PyEVMError):
    """
    Class of errors which can be raised during VM execution.
    """
    burns_gas = True
    erases_return_data = True


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


class ContractCreationCollision(VMError):
    """
    Error signaling that there was an address collision during contract creation.
    """
    pass


class Revert(VMError):
    """
    Error used by the REVERT opcode
    """
    burns_gas = False
    erases_return_data = False


class WriteProtection(VMError):
    """
    Error raised if an attempt to modify the state database is made while
    operating inside of a STATICCALL context.
    """
    pass


class OutOfBoundsRead(VMError):
    """
    Error raised to indicate an attempt was made to read data beyond the
    boundaries of the buffer (such as with RETURNDATACOPY)
    """
    pass
