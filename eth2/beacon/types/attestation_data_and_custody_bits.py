import ssz
from ssz.sedes import boolean

from .attestation_data import AttestationData, default_attestation_data


class AttestationDataAndCustodyBit(ssz.Serializable):

    fields = [
        # Attestation data
        ("data", AttestationData),
        # Custody bit
        ("custody_bit", boolean),
    ]

    def __init__(
        self,
        data: AttestationData = default_attestation_data,
        custody_bit: bool = False,
    ) -> None:
        super().__init__(data=data, custody_bit=custody_bit)

    def __str__(self) -> str:
        return f"data=({self.data}), custody_bit={'0b1' if self.custody_bit else '0b0'}"
