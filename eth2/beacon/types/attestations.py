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
        ('aggregation_bitfield', byte_list),
        ('data', AttestationData),
        ('custody_bitfield', byte_list),
        ('signature', bytes96),
    ]

    def __init__(self,
                 aggregation_bitfield: Bitfield=Bitfield(),
                 data: AttestationData=AttestationData(),
                 custody_bitfield: Bitfield=Bitfield(),
                 signature: BLSSignature=EMPTY_SIGNATURE) -> None:
        super().__init__(
            aggregation_bitfield,
            data,
            custody_bitfield,
            signature,
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
                 custody_bit_0_indices: Sequence[ValidatorIndex]=tuple(),
                 custody_bit_1_indices: Sequence[ValidatorIndex]=tuple(),
                 data: AttestationData=AttestationData(),
                 signature: BLSSignature=EMPTY_SIGNATURE) -> None:
        super().__init__(
            custody_bit_0_indices,
            custody_bit_1_indices,
            data,
            signature,
        )

    def __repr__(self) -> str:
        return f"<IndexedAttestation {self.data}>"
