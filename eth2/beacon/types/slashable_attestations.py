from typing import (
    Sequence,
    Tuple,
)

import rlp
from rlp.sedes import (
    binary,
    CountableList,
)
from eth_typing import (
    Hash32,
)
from eth2._utils.bitfield import (
    has_voted,
)
from eth2.beacon._utils.hash import hash_eth2
from eth2.beacon.sedes import (
    uint64,
)
from eth2.beacon.typing import (
    BLSSignature,
    ValidatorIndex,
)
from eth2.beacon.constants import EMPTY_SIGNATURE

from .attestation_data import AttestationData
from .attestation_data_and_custody_bits import AttestationDataAndCustodyBit


class SlashableAttestation(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Validator indices
        ('validator_indices', CountableList(uint64)),
        # Attestation data
        ('data', AttestationData),
        # Custody bitfield
        ('custody_bitfield', binary),
        # Aggregate signature
        ('aggregate_signature', binary),
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

    _hash = None

    @property
    def hash(self) -> Hash32:
        if self._hash is None:
            self._hash = hash_eth2(rlp.encode(self.data))
        return self._hash

    @property
    def root(self) -> Hash32:
        # Alias of `hash`.
        # Using flat hash, will likely use SSZ tree hash.
        return self.hash

    @property
    def is_custody_bitfield_empty(self) -> bool:
        return self.custody_bitfield == b'\x00' * len(self.custody_bitfield)

    @property
    def is_validator_indices_ascending(self) -> bool:
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
    def messages(self) -> Tuple[Hash32, Hash32]:
        """
        Build the messages that validators are expected to sign for an
        ``AttesterSlashing`` operation.
        """
        # TODO: change to hash_tree_root when we have SSZ tree hashing
        return (
            AttestationDataAndCustodyBit(self.data, False).root,
            AttestationDataAndCustodyBit(self.data, True).root,
        )
