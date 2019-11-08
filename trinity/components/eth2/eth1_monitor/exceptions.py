class Eth1MonitorError(Exception):
    pass


class Eth1Forked(Eth1MonitorError):
    """
    Raised when a fork is detected in Eth1 by `Eth1Monitor`.
    """


class Eth1BlockNotFound(Eth1MonitorError):
    pass
