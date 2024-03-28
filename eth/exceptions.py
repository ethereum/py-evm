from eth_typing import (
    Hash32,
)


class PyEVMError(Exception):
    """
    Base class for all py-evm errors.
    """


class VMNotFound(PyEVMError):
    """
    Raised when no VM is available for the provided block number.
    """


class StateRootNotFound(PyEVMError):
    """
    Raised when the requested state root is not present in our DB.
    """

    @property
    def missing_state_root(self) -> Hash32:
        return self.args[0]


class HeaderNotFound(PyEVMError):
    """
    Raised when a header with the given number/hash does not exist.
    """


class BlockNotFound(PyEVMError):
    """
    Raised when the block with the given number/hash does not exist.
    This will happen, for example, if the transactions or uncles are not
    saved in the database.
    """


class TransactionNotFound(PyEVMError):
    """
    Raised when the transaction with the given hash or block index does not exist.
    """


class UnrecognizedTransactionType(PyEVMError):
    """
    Raised when an encoded transaction is using a first byte that is valid, but
    unrecognized. According to EIP 2718, the byte may be in the range [0, 0x7f].
    As of the Berlin hard fork, all of those versions are undefined, except for
    0x01 in EIP 2930.
    """

    @property
    def type_int(self) -> int:
        return self.args[0]


class ReceiptNotFound(PyEVMError):
    """
    Raised when the Receipt with the given receipt index does not exist.
    """


class ParentNotFound(HeaderNotFound):
    """
    Raised when the parent of a given block does not exist.
    """


class CanonicalHeadNotFound(PyEVMError):
    """
    Raised when the chain has no canonical head.
    """


class GapTrackingCorrupted(PyEVMError):
    """
    Raised when the tracking of chain gaps appears to be corrupted
    (e.g. overlapping gaps)
    """


class CheckpointsMustBeCanonical(PyEVMError):
    """
    Raised when a persisted header attempts to de-canonicalize a checkpoint
    """


class Halt(PyEVMError):
    """
    Raised when an opcode function halts vm execution.
    """


class VMError(PyEVMError):
    """
    Base class for errors raised during VM execution.
    """

    burns_gas = True
    erases_return_data = True


class OutOfGas(VMError):
    """
    Raised when a VM execution has run out of gas.
    """


class InsufficientStack(VMError):
    """
    Raised when the stack is empty.
    """


class FullStack(VMError):
    """
    Raised when the stack is full.
    """


class InvalidJumpDestination(VMError):
    """
    Raised when the jump destination for a JUMPDEST operation is invalid.
    """


class InvalidInstruction(VMError):
    """
    Raised when an opcode is invalid.
    """


class InsufficientFunds(VMError):
    """
    Raised when an account has insufficient funds to transfer the
    requested value.
    """


class StackDepthLimit(VMError):
    """
    Raised when the call stack has exceeded it's maximum allowed depth.
    """


class ContractCreationCollision(VMError):
    """
    Raised when there was an address collision during contract creation.
    """


class IncorrectContractCreationAddress(VMError):
    """
    Raised when the address provided by transaction does not
    match the calculated contract creation address.
    """


class Revert(VMError):
    """
    Raised when the REVERT opcode occurred
    """

    burns_gas = False
    erases_return_data = False


class WriteProtection(VMError):
    """
    Raised when an attempt to modify the state database is made while
    operating inside of a STATICCALL context.
    """


class OutOfBoundsRead(VMError):
    """
    Raised when an attempt was made to read data beyond the
    boundaries of the buffer (such as with RETURNDATACOPY)
    """


class ReservedBytesInCode(VMError):
    """
    Raised when bytes for the code to be deployed are reserved
    for a particular reason.
    """
