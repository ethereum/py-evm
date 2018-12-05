from typing import (
    Sequence,
)

from eth_typing import (
    Hash32,
)
from eth_utils import (
    encode_hex,
)
import rlp
from rlp.sedes import (
    CountableList,
)


from eth.rlp.sedes import (
    hash32,
    uint64,
    uint256,
)
from eth.utils.blake import blake

from .attestation_records import AttestationRecord
from .special_records import SpecialRecord


class BaseBeaconBlock(rlp.Serializable):
    fields = [
        # Slot number
        ('slot', uint64),
        # Proposer RANDAO reveal
        ('randao_reveal', hash32),
        # Recent PoW receipt root
        ('candidate_pow_receipt_root', hash32),
        # Skip list of previous beacon block hashes
        # i'th item is the most recent ancestor whose slot is a multiple of 2**i for i = 0, ..., 31
        ('ancestor_hashes', CountableList(hash32)),
        # State root
        ('state_root', hash32),
        # Attestations
        ('attestations', CountableList(AttestationRecord)),
        # Specials (e.g. logouts, penalties)
        ('specials', CountableList(SpecialRecord)),
        # Proposer signature
        ('proposer_signature', CountableList(uint256)),
    ]

    def __init__(self,
                 slot: int,
                 randao_reveal: Hash32,
                 candidate_pow_receipt_root: Hash32,
                 ancestor_hashes: Sequence[Hash32],
                 state_root: Hash32,
                 attestations: Sequence[AttestationRecord],
                 specials: Sequence[SpecialRecord],
                 proposer_signature: Sequence[int]=None) -> None:
        if proposer_signature is None:
            proposer_signature = (0, 0)
        super().__init__(
            slot=slot,
            randao_reveal=randao_reveal,
            candidate_pow_receipt_root=candidate_pow_receipt_root,
            ancestor_hashes=ancestor_hashes,
            state_root=state_root,
            attestations=attestations,
            specials=specials,
            proposer_signature=proposer_signature,
        )

    def __repr__(self) -> str:
        return '<Block #{0} {1}>'.format(
            self.slot,
            encode_hex(self.hash)[2:10],
        )

    _hash = None

    @property
    def hash(self) -> Hash32:
        if self._hash is None:
            self._hash = blake(rlp.encode(self))
        return self._hash

    @property
    def num_attestations(self) -> int:
        return len(self.attestations)

    @property
    def parent_hash(self) -> Hash32:
        if not self.ancestor_hashes:
            return None
        else:
            return self.ancestor_hashes[0]
