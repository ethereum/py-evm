from typing import (
    Sequence,
)

import ssz
from ssz.sedes import (
    byte_list,
    bytes96,
    List,
    uint64,
)

from .attestation_data import (
    AttestationData,
)

from eth2.beacon.typing import (
    Bitfield,
    ValidatorIndex,
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

    def __repr__(self) -> str:
        return f"<Attestation {self.data} >"


class IndexedAttestation(ssz.Serializable):

    fields = [
        # Validator indices
        ('custody_bit_0_indices', List(uint64)),
        ('custody_bit_1_indices', List(uint64)),
        # Attestation data
        ('data', AttestationData),
        # Aggregate signature
        ('signature', bytes96),
    ]

    def __init__(self,
                 custody_bit_0_indices: Sequence[ValidatorIndex],
                 custody_bit_1_indices: Sequence[ValidatorIndex],
                 data: AttestationData,
                 signature: BLSSignature) -> None:
        super().__init__(
            custody_bit_0_indices,
            custody_bit_1_indices,
            data,
            signature,
        )

    def __repr__(self) -> str:
        return f"<IndexedAttestation {self.data}>"
