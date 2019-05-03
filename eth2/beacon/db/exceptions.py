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
