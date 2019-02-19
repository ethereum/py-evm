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
        ('data', AttestationData),
        # Attester aggregation bitfield
        ('aggregation_bitfield', bytes_sedes),
        # Proof of custody bitfield
        ('custody_bitfield', bytes_sedes),
        # BLS aggregate signature
        ('aggregate_signature', bytes96),
    ]

    def __init__(self,
                 data: AttestationData,
                 aggregation_bitfield: Bitfield,
                 custody_bitfield: Bitfield,
                 aggregate_signature: BLSSignature=EMPTY_SIGNATURE) -> None:
        super().__init__(
            data,
            aggregation_bitfield,
            custody_bitfield,
            aggregate_signature,
        )
