class InvalidEth1Log(Exception):
    """
    Raised when `Eth1Monitor` receives an invalid deposit log from Eth1.
    """


class Eth1Forked(Exception):
    """
    Raised when a fork is detected in Eth1 by `Eth1Monitor`.
    """
