class BeaconDBException(Exception):
    """
    Base class for exceptions raised by this package.
    """
    pass


class FinalizedHeadNotFound(BeaconDBException):
    """
    Exception raised if no finalized head is set in this database.
    """
    pass


class JustifiedHeadNotFound(BeaconDBException):
    """
    Exception raised if no justified head is set in this database.
    """
    pass


class AttestationRootNotFound(BeaconDBException):
    """
    Exception raised if no attestation root is set in this database.
    """
    pass


class MissingForkChoiceScorings(BeaconDBException):
    """
    Exception raised if a client tries to score a block without providing
    the ability to generate a score via a ``scoring``.
    """
    pass
