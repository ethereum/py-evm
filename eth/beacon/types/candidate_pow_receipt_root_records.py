from eth_typing import (
    Hash32,
)
import rlp

from eth.rlp.sedes import (
    uint64,
    hash32,
)


class CandidatePoWReceiptRootRecord(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Candidate PoW receipt root
        ('candidate_pow_receipt_root', hash32),
        # Vote count
        ('votes', uint64),
    ]

    def __init__(self,
                 candidate_pow_receipt_root: Hash32,
                 votes: int) -> None:
        super().__init__(
            candidate_pow_receipt_root=candidate_pow_receipt_root,
            votes=votes,
        )
