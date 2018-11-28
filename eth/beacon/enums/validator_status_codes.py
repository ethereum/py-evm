from enum import IntEnum


class ValidatorStatusCode(IntEnum):
    PENDING_ACTIVATION = 0
    ACTIVE = 1
    PENDING_EXIT = 2
    PENDING_WITHDRAW = 3
    WITHDRAWN = 4
    PENALIZED = 127
