import ssz
from ssz.sedes import (
    bytes_sedes,
    bytes96,
)

from .attestation_data import (
    AttestationData,
)

from eth2.beacon.typing import (
    Bitfield,
    BLSSignature,
)
from eth2.beacon.constants import EMPTY_SIGNATURE


class Attestation(ssz.Serializable):

    fields = [
        # Attester aggregation bitfield
        ('aggregation_bitfield', bytes_sedes),
        # Attestation data
        ('data', AttestationData),
        # Proof of custody bitfield
        ('custody_bitfield', bytes_sedes),
        # BLS aggregate signature
        ('aggregate_signature', bytes96),
    ]

    def __init__(self,
                 aggregation_bitfield: Bitfield,
                 data: AttestationData,
                 custody_bitfield: Bitfield,
                 aggregate_signature: BLSSignature=EMPTY_SIGNATURE) -> None:
        super().__init__(
            aggregation_bitfield,
            data,
            custody_bitfield,
            aggregate_signature,
        )
