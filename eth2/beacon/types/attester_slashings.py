import ssz

from .attestations import (
    IndexedAttestation,
    default_indexed_attestation,
)


class AttesterSlashing(ssz.Serializable):

    fields = [
        # First attestation
        ('attestation_1', IndexedAttestation),
        # Second attestation
        ('attestation_2', IndexedAttestation),
    ]

    def __init__(self,
                 attestation_1: IndexedAttestation=default_indexed_attestation,
                 attestation_2: IndexedAttestation=default_indexed_attestation)-> None:
        super().__init__(
            attestation_1,
            attestation_2,
        )
