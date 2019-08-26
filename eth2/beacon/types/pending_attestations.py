import ssz
from ssz.sedes import Bitlist, uint64

from eth2.beacon.typing import Bitfield, ValidatorIndex

from .attestation_data import AttestationData, default_attestation_data
from .defaults import default_bitfield, default_validator_index


class PendingAttestation(ssz.Serializable):

    fields = [
        ("aggregation_bits", Bitlist(1)),
        ("data", AttestationData),
        ("inclusion_delay", uint64),
        ("proposer_index", uint64),
    ]

    def __init__(
        self,
        aggregation_bits: Bitfield = default_bitfield,
        data: AttestationData = default_attestation_data,
        inclusion_delay: int = 0,
        proposer_index: ValidatorIndex = default_validator_index,
    ) -> None:
        super().__init__(
            aggregation_bits=aggregation_bits,
            data=data,
            inclusion_delay=inclusion_delay,
            proposer_index=proposer_index,
        )

    def __repr__(self) -> str:
        return f"<PendingAttestation inclusion_delay={self.inclusion_delay} data={self.data}>"
