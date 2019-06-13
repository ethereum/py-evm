import ssz
from .attestations import IndexedAttestation


class AttesterSlashing(ssz.Serializable):

    fields = [
        # First attestation
        ('attestation_1', IndexedAttestation),
        # Second attestation
        ('attestation_2', IndexedAttestation),
    ]

    def __init__(self,
                 attestation_1: IndexedAttestation=IndexedAttestation(),
                 attestation_2: IndexedAttestation=IndexedAttestation())-> None:
        super().__init__(
            attestation_1,
            attestation_2,
        )
