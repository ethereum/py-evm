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


from .attestation_signed_data import (
    AttestationSignedData,
)


class AttestationRecord(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        ('data', AttestationSignedData),
        # Attester participation bitfield
        ('attester_bitfield', binary),
        # Proof of custody bitfield
        ('poc_bitfield', binary),
        # BLS aggregate signature
        ('aggregate_sig', CountableList(uint256)),
    ]

    def __init__(self,
                 data: AttestationSignedData,
                 attester_bitfield: bytes,
                 poc_bitfield: bytes,
                 aggregate_sig: Sequence[int]=None) -> None:
        if aggregate_sig is None:
            aggregate_sig = (0, 0)

        super().__init__(
            data=data,
            attester_bitfield=attester_bitfield,
            poc_bitfield=poc_bitfield,
            aggregate_sig=aggregate_sig,
        )
