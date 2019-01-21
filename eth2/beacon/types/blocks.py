from abc import (
    ABC,
    abstractmethod,
)

from typing import (
    Sequence,
    TYPE_CHECKING,
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


from eth._utils.datatypes import (
    Configurable,
)
from eth2.beacon.sedes import (
    hash32,
    uint64,
    uint384,
)

from eth2.beacon.constants import EMPTY_SIGNATURE
from eth2.beacon._utils.hash import hash_eth2
from eth2.beacon.typing import (
    SlotNumber,
    BLSSignature,
)


from .attestations import Attestation
from .custody_challenges import CustodyChallenge
from .custody_reseeds import CustodyReseed
from .custody_responses import CustodyResponse
from .casper_slashings import CasperSlashing
from .deposits import Deposit
from .eth1_data import Eth1Data
from .exits import Exit
from .proposer_slashings import ProposerSlashing

if TYPE_CHECKING:
    from eth2.beacon.db.chain import BaseBeaconChainDB  # noqa: F401


class BaseBeaconBlockBody(rlp.Serializable):
    fields = [
        ('proposer_slashings', CountableList(ProposerSlashing)),
        ('casper_slashings', CountableList(CasperSlashing)),
        ('attestations', CountableList(Attestation)),
        ('custody_reseeds', CountableList(CustodyReseed)),
        ('custody_challenges', CountableList(CustodyChallenge)),
        ('custody_responses', CountableList(CustodyResponse)),
        ('deposits', CountableList(Deposit)),
        ('exits', CountableList(Exit)),
    ]

    def __init__(self,
                 proposer_slashings: Sequence[ProposerSlashing],
                 casper_slashings: Sequence[CasperSlashing],
                 attestations: Sequence[Attestation],
                 custody_reseeds: Sequence[CustodyReseed],
                 custody_challenges: Sequence[CustodyResponse],
                 custody_responses: Sequence[CustodyResponse],
                 deposits: Sequence[Deposit],
                 exits: Sequence[Exit])-> None:
        super().__init__(
            proposer_slashings=proposer_slashings,
            casper_slashings=casper_slashings,
            attestations=attestations,
            custody_reseeds=custody_reseeds,
            custody_challenges=custody_challenges,
            custody_responses=custody_responses,
            deposits=deposits,
            exits=exits,
        )

    @classmethod
    def create_empty_body(cls) -> 'BeaconBlockBody':
        return cls(
            proposer_slashings=(),
            casper_slashings=(),
            attestations=(),
            custody_reseeds=(),
            custody_challenges=(),
            custody_responses=(),
            deposits=(),
            exits=(),
        )

    @property
    def is_empty(self) -> bool:
        return (
            self.proposer_slashings == () and
            self.casper_slashings == () and
            self.attestations == () and
            self.custody_reseeds == () and
            self.custody_challenges == () and
            self.custody_responses == () and
            self.deposits == () and
            self.exits == ()
        )


class BaseBeaconBlock(rlp.Serializable, Configurable, ABC):
    block_body_class = BaseBeaconBlockBody

    fields = [
        #
        # Header
        #
        ('slot', uint64),
        ('parent_root', hash32),
        ('state_root', hash32),
        ('randao_reveal', hash32),
        ('eth1_data', Eth1Data),
        ('signature', CountableList(uint384)),

        #
        # Body
        #
        ('body', block_body_class),
    ]

    def __init__(self,
                 slot: SlotNumber,
                 parent_root: Hash32,
                 state_root: Hash32,
                 randao_reveal: Hash32,
                 eth1_data: Eth1Data,
                 body: BaseBeaconBlockBody,
                 signature: BLSSignature=EMPTY_SIGNATURE) -> None:
        super().__init__(
            slot=slot,
            parent_root=parent_root,
            state_root=state_root,
            randao_reveal=randao_reveal,
            eth1_data=eth1_data,
            signature=signature,
            body=body,
        )

    def __repr__(self) -> str:
        return '<Block #{0} {1}>'.format(
            self.slot,
            encode_hex(self.root)[2:10],
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
        # Using flat hash, might change to SSZ tree hash.
        return self.hash

    @property
    def num_attestations(self) -> int:
        return len(self.body.attestations)

    @property
    def block_without_signature_root(self) -> Hash32:
        return self.copy(
            signature=EMPTY_SIGNATURE
        ).root

    @classmethod
    @abstractmethod
    def from_root(cls, root: Hash32, chaindb: 'BaseBeaconChainDB') -> 'BaseBeaconBlock':
        """
        Return the block denoted by the given block root.
        """
        raise NotImplementedError("Must be implemented by subclasses")


class BeaconBlockBody(BaseBeaconBlockBody):
    pass


class BeaconBlock(BaseBeaconBlock):
    block_body_class = BeaconBlockBody

    @classmethod
    def from_root(cls, root: Hash32, chaindb: 'BaseBeaconChainDB') -> 'BeaconBlock':
        """
        Returns the block denoted by the given block header.
        """
        block = chaindb.get_block_by_root(root, cls)
        body = cls.block_body_class(
            proposer_slashings=block.body.proposer_slashings,
            casper_slashings=block.body.casper_slashings,
            attestations=block.body.attestations,
            custody_reseeds=block.body.custody_reseeds,
            custody_challenges=block.body.custody_challenges,
            custody_responses=block.body.custody_responses,
            deposits=block.body.deposits,
            exits=block.body.exits,
        )

        return cls(
            slot=block.slot,
            parent_root=block.parent_root,
            state_root=block.state_root,
            randao_reveal=block.randao_reveal,
            eth1_data=block.eth1_data,
            signature=block.signature,
            body=body,
        )
