import ssz
from ssz.sedes import (
    boolean,
)
from eth_typing import (
    Hash32,
)

from eth2.beacon._utils.hash import (
    hash_eth2,
)

from .attestation_data import (
    AttestationData,
)


class AttestationDataAndCustodyBit(ssz.Serializable):

    fields = [
        # Attestation data
        ('data', AttestationData),
        # Custody bit
        ('custody_bit', boolean),
    ]

    def __init__(self,
                 data: AttestationData,
                 custody_bit: bool)-> None:

        super().__init__(
            data=data,
            custody_bit=custody_bit,
        )

    _hash = None

    @property
    def hash(self) -> Hash32:
        if self._hash is None:
            self._hash = hash_eth2(ssz.encode(self))
        return self._hash

    @property
    def root(self) -> Hash32:
        # Alias of `hash`.
        # Using flat hash, will likely use SSZ tree hash.
        return self.hash
