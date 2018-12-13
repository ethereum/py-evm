from enum import IntEnum


class SignatureDomain(IntEnum):
    DOMAIN_DEPOSIT = 0
    DOMAIN_ATTESTATION = 1
    DOMAIN_PROPOSAL = 2
    DOMAIN_LOGOUT = 3
