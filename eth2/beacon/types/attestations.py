import rlp
from rlp.sedes import (
    binary,
)

from .attestation_data import (
    AttestationData,
)

from eth2.beacon.typing import (
    Bitfield,
    BLSSignature,
)
from eth2.beacon.constants import EMPTY_SIGNATURE


class Attestation(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        ('data', AttestationData),
        # Attester participation bitfield
        ('aggregation_bitfield', binary),
        # Proof of custody bitfield
        ('custody_bitfield', binary),
        # BLS aggregate signature
        ('aggregate_signature', binary),
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
