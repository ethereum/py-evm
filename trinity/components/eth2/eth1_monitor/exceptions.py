from eth_utils import ValidationError


class Eth1MonitorError(Exception):
    pass


class Eth1MonitorValidationError(ValidationError, Eth1MonitorError):
    pass


class Eth1BlockNotFound(Eth1MonitorError):
    pass
