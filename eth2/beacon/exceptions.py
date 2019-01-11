from eth.exceptions import (
    PyEVMError,
)


class SMNotFound(PyEVMError):
    """
    Raise when no StateMachine is available for the provided block slot number.
    """
    pass
