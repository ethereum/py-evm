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

from .attestations import Attestation
from .proposer_slashings import ProposerSlashing
from .casper_slashings import CasperSlashing
from .deposits import Deposit
from .exits import Exit


class BeaconBlockBody(rlp.Serializable):
    fields = [
        ('attestations', CountableList(Attestation)),
        ('proposer_slashings', CountableList(ProposerSlashing)),
        ('casper_slashings', CountableList(CasperSlashing)),
        ('deposits', CountableList(Deposit)),
        ('exits', CountableList(Exit)),
    ]

    def __init__(self,
                 attestations: Sequence[int],
                 proposer_slashings: Sequence[int],
                 casper_slashings: Sequence[int],
                 deposits: Sequence[int],
                 exits: Sequence[int])-> None:
        super().__init__(
            attestations=attestations,
            proposer_slashings=proposer_slashings,
            casper_slashings=casper_slashings,
            deposits=deposits,
            exits=exits,
        )


class BaseBeaconBlock(rlp.Serializable):
    fields = [
        # Header

        ('slot', uint64),
        # Skip list of previous beacon block hashes
        # i'th item is the most recent ancestor whose slot is a multiple of 2**i for i = 0, ..., 31
        ('ancestor_hashes', CountableList(hash32)),
        ('state_root', hash32),
        ('randao_reveal', hash32),
        ('candidate_pow_receipt_root', hash32),
        ('signature', CountableList(uint256)),

        # Body
        ('body', BeaconBlockBody)
    ]

    def __init__(self,
                 slot: int,
                 ancestor_hashes: Sequence[Hash32],
                 state_root: Hash32,
                 randao_reveal: Hash32,
                 candidate_pow_receipt_root: Hash32,
                 body: BeaconBlockBody,
                 signature: Sequence[int]=None) -> None:
        if signature is None:
            signature = (0, 0)
        super().__init__(
            slot=slot,
            ancestor_hashes=ancestor_hashes,
            state_root=state_root,
            randao_reveal=randao_reveal,
            candidate_pow_receipt_root=candidate_pow_receipt_root,
            signature=signature,
            body=body
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
        return len(self.body.attestations)

    @property
    def parent_hash(self) -> Hash32:
        if not self.ancestor_hashes:
            return None
        else:
            return self.ancestor_hashes[0]
