from enum import IntEnum, unique


@unique
class SignatureDomain(IntEnum):
    DOMAIN_BEACON_PROPOSER = 0
    DOMAIN_BEACON_ATTESTER = 1
    DOMAIN_RANDAO = 2
    DOMAIN_DEPOSIT = 3
    DOMAIN_VOLUNTARY_EXIT = 4
