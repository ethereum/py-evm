from enum import IntEnum


class ValidatorStatusFlags(IntEnum):
    INITIATED_EXIT = 1
    WITHDRAWABLE = 2


class ValidatorRegistryDeltaFlag(IntEnum):
    ACTIVATION = 0
    EXIT = 1


class SignatureDomain(IntEnum):
    DOMAIN_DEPOSIT = 0
    DOMAIN_ATTESTATION = 1
    DOMAIN_PROPOSAL = 2
    DOMAIN_EXIT = 3
