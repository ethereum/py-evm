from typing import (
    Sequence,
)

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
        ('aggregate_sig', CountableList(uint384)),
    ]

    def __init__(self,
                 data: AttestationData,
                 participation_bitfield: bytes,
                 custody_bitfield: bytes,
                 aggregate_sig: Sequence[int]=(0, 0)) -> None:
        super().__init__(
            data,
            participation_bitfield,
            custody_bitfield,
            aggregate_sig,
        )
