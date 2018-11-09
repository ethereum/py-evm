from typing import (
    Iterable,
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


from eth.utils.blake import blake
from eth.constants import (
    ZERO_HASH32,
)
from eth.rlp.sedes import (
    int64,
    hash32,
)

from .attestation_records import AttestationRecord


class BaseBeaconBlock(rlp.Serializable):
    fields = [
        # Hash of the parent block
        ('parent_hash', hash32),
        # Slot number (for the PoS mechanism)
        ('slot_number', int64),
        # Randao commitment reveal
        ('randao_reveal', hash32),
        # Attestations
        ('attestations', CountableList(AttestationRecord)),
        # Reference to PoW chain block
        ('pow_chain_ref', hash32),
        # Hash of the active state
        ('active_state_root', hash32),
        # Hash of the crystallized state
        ('crystallized_state_root', hash32),
    ]

    def __init__(self,
                 parent_hash: Hash32,
                 slot_number: int,
                 randao_reveal: Hash32,
                 attestations: Iterable[AttestationRecord],
                 pow_chain_ref: Hash32,
                 active_state_root: Hash32=ZERO_HASH32,
                 crystallized_state_root: Hash32=ZERO_HASH32) -> None:
        if attestations is None:
            attestations = []

        super().__init__(
            parent_hash=parent_hash,
            slot_number=slot_number,
            randao_reveal=randao_reveal,
            attestations=attestations,
            pow_chain_ref=pow_chain_ref,
            active_state_root=active_state_root,
            crystallized_state_root=crystallized_state_root,
        )

    def __repr__(self) -> str:
        return '<Block #{0} {1}>'.format(
            self.slot_number,
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
