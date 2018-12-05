import rlp
from rlp.sedes import (
    binary,
)

from eth.rlp.sedes import (
    uint64,
)


from .attestation_signed_data import (
    AttestationSignedData,
)


class ProcessedAttestation(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Signed data
        ('data', AttestationSignedData),
        # Attester participation bitfield
        ('attester_bitfield', binary),
        # Proof of custody bitfield
        ('poc_bitfield', binary),
        # Slot in which it was included
        ('slot_included', uint64),
    ]

    def __init__(self,
                 data: AttestationSignedData,
                 attester_bitfield: bytes,
                 poc_bitfield: bytes,
                 slot_included: int) -> None:
        super().__init__(
            data=data,
            attester_bitfield=attester_bitfield,
            poc_bitfield=poc_bitfield,
            slot_included=slot_included,
        )
