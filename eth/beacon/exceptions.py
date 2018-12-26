from eth.exceptions import (
    PyEVMError,
)


class MinEmptyValidatorIndexNotFound(PyEVMError):
    """
    No empty slot in the validator registry
    """
    pass
