from typing import (
    Sequence,
)

import rlp
from rlp.sedes import (
    binary,
    CountableList,
)

from eth.rlp.sedes import (
    uint256,
)


from .attestation_data import (
    AttestationData,
)


class AttestationRecord(rlp.Serializable):
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
        ('aggregate_sig', CountableList(uint256)),
    ]

    def __init__(self,
                 data: AttestationData,
                 participation_bitfield: bytes,
                 custody_bitfield: bytes,
                 aggregate_sig: Sequence[int]=None) -> None:
        if aggregate_sig is None:
            aggregate_sig = (0, 0)

        super().__init__(
            data=data,
            participation_bitfield=participation_bitfield,
            custody_bitfield=custody_bitfield,
            aggregate_sig=aggregate_sig,
        )
