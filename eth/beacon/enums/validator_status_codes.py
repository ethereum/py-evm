from enum import IntEnum


class ValidatorStatusCode(IntEnum):
    PENDING_ACTIVATION = 0
    ACTIVE = 1
    PENDING_EXIT = 2
    EXITED_WITHOUT_PENALTY = 3
    EXITED_WITH_PENALTY = 4
