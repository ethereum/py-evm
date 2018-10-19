from abc import (
    ABC,
)

from typing import (
    Iterable,
    Optional,
    Union,
    overload,
)

from eth_typing import (
    Hash32,
)
import rlp
from rlp.sedes import (
    CountableList,
)

from eth.constants import (
    ZERO_HASH32,
)
from eth.rlp.sedes import (
    int64,
    hash32,
)
from eth.utils.blake import blake
from eth.utils.datatypes import (
    Configurable,
)
from eth.utils.hexadecimal import (
    encode_hex,
)

from .attestation_records import AttestationRecord


BlockParams = Union[
    Optional[int],
    Optional[Iterable[AttestationRecord]],
    Optional[Hash32],
]


class BaseBeaconBlock(rlp.Serializable, Configurable, ABC):
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

    @overload
    def __init__(self, **kwargs: BlockParams) -> None:
        ...

    @overload  # noqa: F811
    def __init__(self,  # noqa: F811
                 parent_hash: Hash32,
                 slot_number: int,
                 randao_reveal: Hash32,
                 pow_chain_ref: Hash32,
                 attestations: Iterable[AttestationRecord]=None,
                 active_state_root: Hash32=ZERO_HASH32,
                 crystallized_state_root: Hash32=ZERO_HASH32) -> None:
        ...

    def __init__(self,  # noqa: F811
                 parent_hash,
                 slot_number,
                 randao_reveal,
                 pow_chain_ref,
                 attestations=None,
                 active_state_root=ZERO_HASH32,
                 crystallized_state_root=ZERO_HASH32):
        if attestations is None:
            attestations = []
        super().__init__(
            parent_hash=parent_hash,
            slot_number=slot_number,
            randao_reveal=randao_reveal,
            pow_chain_ref=pow_chain_ref,
            attestations=attestations,
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

    @property
    def is_genesis(self) -> bool:
        return self.parent_hash == ZERO_HASH32 and self.slot_number == 0

    @classmethod
    def from_parent(cls,
                    parent_block: 'BaseBeaconBlock',
                    slot_number: int=None,
                    randao_reveal: Hash32=None,
                    attestations: Iterable[AttestationRecord]=None,
                    pow_chain_ref: Hash32=None,
                    active_state_root: Hash32=ZERO_HASH32,
                    crystallized_state_root: Hash32=ZERO_HASH32) -> 'BaseBeaconBlock':
        """
        Initialize a new block with the `parent` block as the block's
        parent hash.
        """
        if slot_number is None:
            slot_number = parent_block.slot_number + 1
        if randao_reveal is None:
            randao_reveal = parent_block.randao_reveal
        if attestations is None:
            attestations = ()
        if pow_chain_ref is None:
            pow_chain_ref = parent_block.pow_chain_ref

        block_kwargs = {
            'parent_hash': parent_block.hash,
            'slot_number': slot_number,
            'randao_reveal': randao_reveal,
            'attestations': attestations,
            'pow_chain_ref': pow_chain_ref,
            'active_state_root': active_state_root,
            'crystallized_state_root': crystallized_state_root,
        }

        block = cls(**block_kwargs)
        return block
