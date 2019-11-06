class Eth1MonitorError(Exception):
    pass


class InvalidEth1Log(Eth1MonitorError):
    """
    Raised when `Eth1Monitor` receives an invalid deposit log from Eth1.
    """


class Eth1Forked(Eth1MonitorError):
    """
    Raised when a fork is detected in Eth1 by `Eth1Monitor`.
    """


class Eth1BlockNotFound(Eth1MonitorError):
    pass
