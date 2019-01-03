import rlp
from rlp.sedes import (
    CountableList,
)
from typing import (
    Sequence,
    Tuple,
)
from eth_typing import (
    Hash32,
)
from eth.beacon._utils.hash import hash_eth2
from eth.rlp.sedes import (
    uint24,
    uint384,
)
from eth.beacon.typing import (
    BLSSignature,
    ValidatorIndex,
)
from eth.beacon.constants import EMPTY_SIGNATURE

from .attestation_data import AttestationData
from .attestation_data_and_custody_bits import AttestationDataAndCustodyBit


class SlashableVoteData(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Validator indices with custody bit equal to 0
        ('custody_bit_0_indices', CountableList(uint24)),
        # Validator indices with custody bit equal to 1
        ('custody_bit_1_indices', CountableList(uint24)),
        # Attestation data
        ('data', AttestationData),
        # Aggregate signature
        ('aggregate_signature', CountableList(uint384)),
    ]

    def __init__(self,
                 custody_bit_0_indices: Sequence[ValidatorIndex],
                 custody_bit_1_indices: Sequence[ValidatorIndex],
                 data: AttestationData,
                 aggregate_signature: BLSSignature = EMPTY_SIGNATURE) -> None:
        super().__init__(
            custody_bit_0_indices,
            custody_bit_1_indices,
            data,
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

    _vote_count = None

    @property
    def vote_count(self) -> int:
        if self._vote_count is None:
            count_zero_indices = len(self.custody_bit_0_indices)
            count_one_indices = len(self.custody_bit_1_indices)
            self._vote_count = count_zero_indices + count_one_indices
        return self._vote_count

    @property
    def messages(self) -> Tuple[Hash32, Hash32]:
        """
        Build the messages that validators are expected to sign for a ``CasperSlashing`` operation.
        """
        # TODO: change to hash_tree_root when we have SSZ tree hashing
        return (
            AttestationDataAndCustodyBit(self.data, False).root,
            AttestationDataAndCustodyBit(self.data, True).root,
        )
