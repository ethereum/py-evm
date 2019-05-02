from typing import (
    Sequence,
    Tuple,
)

import ssz
from ssz.sedes import (
    List,
    byte_list,
    bytes96,
    uint64,
)

from eth_typing import (
    BLSSignature,
    Hash32,
)
from eth2._utils.bitfield import (
    has_voted,
)
from eth2.beacon.typing import (
    ValidatorIndex,
)
from eth2.beacon.constants import EMPTY_SIGNATURE

from .attestation_data import AttestationData
from .attestation_data_and_custody_bits import AttestationDataAndCustodyBit


class SlashableAttestation(ssz.Serializable):

    fields = [
        # Validator indices
        ('validator_indices', List(uint64)),
        # Attestation data
        ('data', AttestationData),
        # Custody bitfield
        ('custody_bitfield', byte_list),
        # Aggregate signature
        ('aggregate_signature', bytes96),
    ]

    def __init__(self,
                 validator_indices: Sequence[ValidatorIndex],
                 data: AttestationData,
                 custody_bitfield: bytes,
                 aggregate_signature: BLSSignature = EMPTY_SIGNATURE) -> None:
        super().__init__(
            validator_indices,
            data,
            custody_bitfield,
            aggregate_signature,
        )

    @property
    def are_validator_indices_ascending(self) -> bool:
        for i in range(len(self.validator_indices) - 1):
            if self.validator_indices[i] >= self.validator_indices[i + 1]:
                return False
        return True

    @property
    def custody_bit_indices(self) -> Tuple[Tuple[ValidatorIndex, ...], Tuple[ValidatorIndex, ...]]:
        custody_bit_0_indices = ()  # type: Tuple[ValidatorIndex, ...]
        custody_bit_1_indices = ()  # type: Tuple[ValidatorIndex, ...]
        for i, validator_index in enumerate(self.validator_indices):
            if not has_voted(self.custody_bitfield, i):
                custody_bit_0_indices += (validator_index,)
            else:
                custody_bit_1_indices += (validator_index,)

        return (custody_bit_0_indices, custody_bit_1_indices)

    @property
    def message_hashes(self) -> Tuple[Hash32, Hash32]:
        """
        Build the message_hashes that validators are expected to sign for an
        ``AttesterSlashing`` operation.
        """
        return (
            AttestationDataAndCustodyBit(data=self.data, custody_bit=False).root,
            AttestationDataAndCustodyBit(data=self.data, custody_bit=True).root,
        )
