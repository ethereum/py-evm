from eth.exceptions import (
    PyEVMError,
)

from eth_utils import (
    ValidationError,
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


class InvalidEpochError(ValidationError):
    """
    Raised when a function receives a query for an epoch that is not semantically valid.

    Example: asking the ``BeaconState`` about an epoch that is not derivable given the current data.
    """
    pass


class SignatureError(ValidationError):
    """
    Raised when a verification of public keys, messages, and signature fails.
    """
    pass
