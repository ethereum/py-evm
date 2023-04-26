from eth.exceptions import (
    PyEVMError,
)


class SnapshotNotFound(PyEVMError):
    """
    Raised when a requested snapshot could not be found.
    """
