from eth.exceptions import (
    PyEVMError,
)


class MinEmptyValidatorIndexNotFound(PyEVMError):
    """
    No empty slot in the validator registry
    """
    pass


class SMNotFound(PyEVMError):
    """
    Raise when no StateMachine is available for the provided block slot number.
    """
    pass
