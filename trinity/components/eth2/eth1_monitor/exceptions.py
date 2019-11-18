from eth_utils import ValidationError


class Eth1MonitorError(Exception):
    ...


class Eth1MonitorValidationError(ValidationError, Eth1MonitorError):
    ...


class Eth1BlockNotFound(Eth1MonitorError):
    ...


class DepositDataCorrupted(Eth1MonitorError):
    """
    `DepositData` which we have locally is not consistent with the deposit tree on chain.
    """


class DepositDataDBError(Exception):
    ...


class DepositDataDBValidationError(ValidationError, DepositDataDBError):
    ...
