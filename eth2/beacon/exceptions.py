from eth.exceptions import (
    PyEVMError,
)


class StateMachineNotFound(PyEVMError):
    """
    Raised when no ``StateMachine`` is available for the provided block slot number.
    """
    pass


class BlockClassError(PyEVMError):
    """
    Raised when the given ``block`` doesn't match the block class version
    """
    pass
