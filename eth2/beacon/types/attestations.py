from typing import Sequence

from eth_typing import BLSSignature
from eth_utils import humanize_hash
import ssz
from ssz.sedes import Bitlist, List, bytes96, uint64

from eth2.beacon.constants import EMPTY_SIGNATURE
from eth2.beacon.typing import Bitfield, ValidatorIndex

from .attestation_data import AttestationData, default_attestation_data
from .defaults import default_bitfield, default_tuple


class Attestation(ssz.Serializable):

    fields = [
        ("aggregation_bits", Bitlist(1)),
        ("data", AttestationData),
        ("signature", bytes96),
    ]

    def __init__(
        self,
        aggregation_bits: Bitfield = default_bitfield,
        data: AttestationData = default_attestation_data,
        signature: BLSSignature = EMPTY_SIGNATURE,
    ) -> None:
        super().__init__(aggregation_bits, data, signature)

    def __str__(self) -> str:
        return (
            f"aggregation_bits={self.aggregation_bits},"
            f" data=({self.data}),"
            f" signature={humanize_hash(self.signature)}"
        )


default_attestation = Attestation()


class IndexedAttestation(ssz.Serializable):

    fields = [
        # Validator indices
        ("attesting_indices", List(uint64, 1)),
        # Attestation data
        ("data", AttestationData),
        # Aggregate signature
        ("signature", bytes96),
    ]

    def __init__(
        self,
        attesting_indices: Sequence[ValidatorIndex] = default_tuple,
        data: AttestationData = default_attestation_data,
        signature: BLSSignature = EMPTY_SIGNATURE,
    ) -> None:
        super().__init__(attesting_indices, data, signature)

    def __str__(self) -> str:
        return (
            f"attesting_indices={self.attesting_indices},"
            f" data=({self.data}),"
            f" signature={humanize_hash(self.signature)}"
        )


default_indexed_attestation = IndexedAttestation()
