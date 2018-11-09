from typing import (
    Iterable,
)

import rlp
from rlp.sedes import (
    CountableList,
)
from eth_typing import (
    Hash32,
)
from eth_utils import (
    encode_hex,
)

from eth.rlp.sedes import (
    hash32
)
from eth.utils.blake import (
    blake,
)

from .attestation_records import AttestationRecord


class ActiveState(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Attestations that have not yet been processed
        ('pending_attestations', CountableList(AttestationRecord)),
        # Most recent 2*CYCLE_LENGTH block hashes, older to newer
        ('recent_block_hashes', CountableList(hash32)),
    ]

    def __init__(self,
                 pending_attestations: Iterable[AttestationRecord]=None,
                 recent_block_hashes: Iterable[Hash32]=None) -> None:
        if pending_attestations is None:
            pending_attestations = ()
        if recent_block_hashes is None:
            recent_block_hashes = ()

        super().__init__(
            pending_attestations=pending_attestations,
            recent_block_hashes=recent_block_hashes,
        )

    def __repr__(self) -> str:
        return '<ActiveState #{0}>'.format(
            encode_hex(self.hash)[2:10],
        )

    _hash = None

    @property
    def hash(self) -> Hash32:
        if self._hash is None:
            self._hash = blake(rlp.encode(self))
        return self._hash

    @property
    def num_pending_attestations(self) -> int:
        return len(self.pending_attestations)

    @property
    def num_recent_block_hashes(self) -> int:
        return len(self.recent_block_hashes)
