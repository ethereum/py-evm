from enum import IntEnum

from eth2.beacon.typing import (
    DomainType,
)


class SignatureDomain(IntEnum):
    DOMAIN_BEACON_PROPOSER = 0
    DOMAIN_RANDAO = 1
    DOMAIN_ATTESTATION = 2
    DOMAIN_DEPOSIT = 3
    DOMAIN_VOLUNTARY_EXIT = 4
    DOMAIN_TRANSFER = 5

    def __get__(self, obj, obj_type) -> DomainType:
        return self.to_bytes(4, "little")
