import rlp
from .slashable_attestations import SlashableAttestation


class AttesterSlashing(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # First slashable attestation
        ('slashable_attestation_1', SlashableAttestation),
        # Second slashable attestation
        ('slashable_attestation_2', SlashableAttestation),
    ]

    def __init__(self,
                 slashable_attestation_1: SlashableAttestation,
                 slashable_attestation_2: SlashableAttestation)-> None:
        super().__init__(
            slashable_attestation_1,
            slashable_attestation_2,
        )
