import ssz
from ssz.sedes import (
    boolean,
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
