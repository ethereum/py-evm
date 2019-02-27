from enum import IntEnum


class SignatureDomain(IntEnum):
    DOMAIN_DEPOSIT = 0
    DOMAIN_ATTESTATION = 1
    DOMAIN_PROPOSAL = 2
    DOMAIN_EXIT = 3
    DOMAIN_RANDAO = 4
