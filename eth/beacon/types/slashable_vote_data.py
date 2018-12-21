import rlp
from rlp.sedes import (
    CountableList,
)
from typing import (
    Sequence,
)
from eth_typing import (
    Hash32,
)
from eth.beacon._utils.hash import hash_eth2
from eth.rlp.sedes import (
    uint24,
    uint384,
)
from .attestation_data import AttestationData


class SlashableVoteData(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Proof-of-custody indices (0 bits)
        ('aggregate_signature_poc_0_indices', CountableList(uint24)),
        # Proof-of-custody indices (1 bits)
        ('aggregate_signature_poc_1_indices', CountableList(uint24)),
        # Attestation data
        ('data', AttestationData),
        # Aggregate signature
        ('aggregate_signature', CountableList(uint384)),
    ]

    def __init__(self,
                 aggregate_signature_poc_0_indices: Sequence[int],
                 aggregate_signature_poc_1_indices: Sequence[int],
                 data: AttestationData,
                 aggregate_signature: Sequence[int]) -> None:
        super().__init__(
            aggregate_signature_poc_0_indices,
            aggregate_signature_poc_1_indices,
            data,
            aggregate_signature,
        )

    _hash = None

    @property
    def hash(self) -> Hash32:
        if self._hash is None:
            self._hash = hash_eth2(rlp.encode(self))
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
            count_zero_indices = len(self.aggregate_signature_poc_0_indices)
            count_one_indices = len(self.aggregate_signature_poc_1_indices)
            self._vote_count = count_zero_indices + count_one_indices
        return self._vote_count
