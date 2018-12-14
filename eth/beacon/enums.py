from enum import IntEnum


class ValidatorStatusCode(IntEnum):
    PENDING_ACTIVATION = 0
    ACTIVE = 1
    ACTIVE_PENDING_EXIT = 2
    EXITED_WITHOUT_PENALTY = 3
    EXITED_WITH_PENALTY = 4


class ValidatorRegistryDeltaFlag(IntEnum):
    ACTIVATION = 0
    EXIT = 1


class SignatureDomain(IntEnum):
    DOMAIN_DEPOSIT = 0
    DOMAIN_ATTESTATION = 1
    DOMAIN_PROPOSAL = 2
    DOMAIN_EXIT = 3
