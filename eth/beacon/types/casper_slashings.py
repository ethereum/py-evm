import rlp
from rlp.sedes import (
    CountableList,
)
from typing import (
    Sequence,
)

from eth.rlp.sedes import (
    uint24,
    uint256,
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
        ('aggregate_signature', CountableList(uint256)),
    ]

    def __init__(self,
                 aggregate_signature_poc_0_indices: Sequence[int],
                 aggregate_signature_poc_1_indices: Sequence[int],
                 data: AttestationData,
                 aggregate_signature: Sequence[int]) -> None:
        super().__init__(
            aggregate_signature_poc_0_indices=aggregate_signature_poc_0_indices,
            aggregate_signature_poc_1_indices=aggregate_signature_poc_1_indices,
            data=data,
            aggregate_signature=aggregate_signature,
        )


class CasperSlashing(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # First batch of votes
        ('votes_1', SlashableVoteData),
        # Second batch of votes
        ('votes_2', SlashableVoteData),
    ]

    def __init__(self,
                 votes_1: SlashableVoteData,
                 votes_2: SlashableVoteData)-> None:
        super().__init__(
            votes_1=votes_1,
            votes_2=votes_2,
        )
