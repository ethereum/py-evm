import ssz
from ssz.sedes import (
    byte_list,
    bytes96,
)

from .attestation_data import (
    AttestationData,
)

from eth2.beacon.typing import (
    Bitfield,
)
from eth2.beacon.constants import EMPTY_SIGNATURE
from eth_typing import (
    BLSSignature,
)


class Attestation(ssz.Serializable):

    fields = [
        # Attester aggregation bitfield
        ('aggregation_bitfield', byte_list),
        # Attestation data
        ('data', AttestationData),
        # Proof of custody bitfield
        ('custody_bitfield', byte_list),
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
