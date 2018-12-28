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
    BLSSignatureAggregated,
)
from eth.beacon.constants import EMPTY_SIGNATURE

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
                 aggregate_signature: BLSSignatureAggregated = EMPTY_SIGNATURE) -> None:
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
            count_zero_indices = len(self.aggregate_signature_poc_0_indices)
            count_one_indices = len(self.aggregate_signature_poc_1_indices)
            self._vote_count = count_zero_indices + count_one_indices
        return self._vote_count

    @property
    def messages(self) -> Tuple[bytes, bytes]:
        """
        Build the messages that validators are expected to sign for a ``CasperSlashing`` operation.
        """
        # TODO: change to hash_tree_root(vote_data) when we have SSZ tree hashing
        vote_data_root = self.root
        return (
            vote_data_root + (0).to_bytes(1, 'big'),
            vote_data_root + (1).to_bytes(1, 'big'),
        )
