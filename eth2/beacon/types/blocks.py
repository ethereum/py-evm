from abc import (
    ABC,
    abstractmethod,
)

from typing import (
    Sequence,
    TYPE_CHECKING,
)

from eth_typing import (
    BLSSignature,
    Hash32,
)
from eth_utils import (
    encode_hex,
)

import ssz
from ssz.sedes import (
    List,
    bytes32,
    bytes96,
    uint64,
)


from eth._utils.datatypes import (
    Configurable,
)

from eth2.beacon._utils.hash import hash_eth2
from eth2.beacon.constants import EMPTY_SIGNATURE
from eth2.beacon.typing import (
    Slot,
    FromBlockParams,
)


from .attestations import Attestation
from .attester_slashings import AttesterSlashing
from .deposits import Deposit
from .eth1_data import Eth1Data
from .transfers import Transfer
from .voluntary_exits import VoluntaryExit
from .proposer_slashings import ProposerSlashing

if TYPE_CHECKING:
    from eth2.beacon.db.chain import BaseBeaconChainDB  # noqa: F401


class BeaconBlockBody(ssz.Serializable):

    fields = [
        ('proposer_slashings', List(ProposerSlashing)),
        ('attester_slashings', List(AttesterSlashing)),
        ('attestations', List(Attestation)),
        ('deposits', List(Deposit)),
        ('voluntary_exits', List(VoluntaryExit)),
        ('transfers', List(Transfer)),
    ]

    def __init__(self,
                 proposer_slashings: Sequence[ProposerSlashing],
                 attester_slashings: Sequence[AttesterSlashing],
                 attestations: Sequence[Attestation],
                 deposits: Sequence[Deposit],
                 voluntary_exits: Sequence[VoluntaryExit],
                 transfers: Sequence[Transfer])-> None:
        super().__init__(
            proposer_slashings=proposer_slashings,
            attester_slashings=attester_slashings,
            attestations=attestations,
            deposits=deposits,
            voluntary_exits=voluntary_exits,
            transfers=transfers,
        )

    @classmethod
    def create_empty_body(cls) -> 'BeaconBlockBody':
        return cls(
            proposer_slashings=(),
            attester_slashings=(),
            attestations=(),
            deposits=(),
            voluntary_exits=(),
            transfers=(),
        )

    @property
    def is_empty(self) -> bool:
        return (
            self.proposer_slashings == () and
            self.attester_slashings == () and
            self.attestations == () and
            self.deposits == () and
            self.voluntary_exits == () and
            self.transfers == ()
        )

    @classmethod
    def cast_block_body(cls,
                        body: 'BeaconBlockBody') -> 'BeaconBlockBody':
        return cls(
            proposer_slashings=body.proposer_slashings,
            attester_slashings=body.attester_slashings,
            attestations=body.attestations,
            deposits=body.deposits,
            voluntary_exits=body.voluntary_exits,
            transfers=body.transfers,
        )

    _hash = None

    @property
    def hash(self) -> Hash32:
        if self._hash is None:
            self._hash = hash_eth2(ssz.encode(self))
        return self._hash

    @property
    def root(self) -> Hash32:
        # TODO use `hash_tree_root` in lieu of `hash` here
        # Alias of `hash`.
        # Using flat hash, might change to SSZ tree hash.
        return self.hash


class BaseBeaconBlock(ssz.Serializable, Configurable, ABC):
    fields = [
        #
        # Header
        #
        ('slot', uint64),
        ('previous_block_root', bytes32),
        ('state_root', bytes32),
        ('randao_reveal', bytes96),
        ('eth1_data', Eth1Data),
        ('signature', bytes96),

        #
        # Body
        #
        ('body', BeaconBlockBody),
    ]

    def __init__(self,
                 slot: Slot,
                 previous_block_root: Hash32,
                 state_root: Hash32,
                 randao_reveal: BLSSignature,
                 eth1_data: Eth1Data,
                 body: BeaconBlockBody,
                 signature: BLSSignature=EMPTY_SIGNATURE) -> None:
        super().__init__(
            slot=slot,
            previous_block_root=previous_block_root,
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
            self._hash = hash_eth2(ssz.encode(self))
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


class BeaconBlock(BaseBeaconBlock):
    block_body_class = BeaconBlockBody

    @classmethod
    def from_root(cls, root: Hash32, chaindb: 'BaseBeaconChainDB') -> 'BeaconBlock':
        """
        Return the block denoted by the given block ``root``.
        """
        block = chaindb.get_block_by_root(root, cls)
        body = cls.block_body_class(
            proposer_slashings=block.body.proposer_slashings,
            attester_slashings=block.body.attester_slashings,
            attestations=block.body.attestations,
            deposits=block.body.deposits,
            voluntary_exits=block.body.voluntary_exits,
            transfers=block.body.transfer,
        )

        return cls(
            slot=block.slot,
            previous_block_root=block.previous_block_root,
            state_root=block.state_root,
            randao_reveal=block.randao_reveal,
            eth1_data=block.eth1_data,
            signature=block.signature,
            body=body,
        )

    @classmethod
    def from_parent(cls,
                    parent_block: 'BaseBeaconBlock',
                    block_params: FromBlockParams) -> 'BaseBeaconBlock':
        """
        Initialize a new block with the `parent` block as the block's
        parent hash.
        """
        if block_params.slot is None:
            slot = parent_block.slot + 1
        else:
            slot = block_params.slot

        return cls(
            slot=slot,
            previous_block_root=parent_block.root,
            state_root=parent_block.state_root,
            randao_reveal=EMPTY_SIGNATURE,
            eth1_data=parent_block.eth1_data,
            signature=EMPTY_SIGNATURE,
            body=cls.block_body_class.create_empty_body(),
        )

    @classmethod
    def convert_block(cls,
                      block: 'BaseBeaconBlock') -> 'BeaconBlock':
        return cls(
            slot=block.slot,
            previous_block_root=block.previous_block_root,
            state_root=block.state_root,
            randao_reveal=block.randao_reveal,
            eth1_data=block.eth1_data,
            signature=block.signature,
            body=block.body,
        )
