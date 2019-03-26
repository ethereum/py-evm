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


class ProposerIndexError(PyEVMError):
    """
    Raised when the given ``validator_index`` doesn't match the ``validator_index``
    of proposer of the given ``slot``
    """
    pass


class NoCommitteeAssignment(PyEVMError):
    """
    Raised when no potential crosslink committee assignment.
    """
    pass
