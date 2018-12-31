import rlp
from rlp.sedes import (
    binary,
    CountableList,
)

from eth.rlp.sedes import (
    uint384,
)


from .attestation_data import (
    AttestationData,
)

from eth.beacon.typing import (
    Bitfield,
    BLSSignature,
)
from eth.beacon.constants import EMPTY_SIGNATURE


class Attestation(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        ('data', AttestationData),
        # Attester participation bitfield
        ('participation_bitfield', binary),
        # Proof of custody bitfield
        ('custody_bitfield', binary),
        # BLS aggregate signature
        ('aggregate_signature', CountableList(uint384)),
    ]

    def __init__(self,
                 data: AttestationData,
                 participation_bitfield: Bitfield,
                 custody_bitfield: Bitfield,
                 aggregate_signature: BLSSignature=EMPTY_SIGNATURE) -> None:
        super().__init__(
            data,
            participation_bitfield,
            custody_bitfield,
            aggregate_signature,
        )
