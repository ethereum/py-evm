from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Sequence

from eth._utils.datatypes import Configurable
from eth.constants import ZERO_HASH32
from eth_typing import BLSSignature, Hash32
from eth_utils import humanize_hash
import ssz
from ssz.sedes import List, bytes32, bytes96, uint64

from eth2.beacon.constants import (
    EMPTY_SIGNATURE,
    GENESIS_PARENT_ROOT,
    ZERO_SIGNING_ROOT,
)
from eth2.beacon.typing import FromBlockParams, SigningRoot, Slot

from .attestations import Attestation
from .attester_slashings import AttesterSlashing
from .block_headers import BeaconBlockHeader
from .defaults import default_slot, default_tuple
from .deposits import Deposit
from .eth1_data import Eth1Data, default_eth1_data
from .proposer_slashings import ProposerSlashing
from .voluntary_exits import VoluntaryExit

if TYPE_CHECKING:
    from eth2.beacon.db.chain import BaseBeaconChainDB  # noqa: F401


class BeaconBlockBody(ssz.Serializable):

    fields = [
        ("randao_reveal", bytes96),
        ("eth1_data", Eth1Data),
        ("graffiti", bytes32),
        ("proposer_slashings", List(ProposerSlashing, 1)),
        ("attester_slashings", List(AttesterSlashing, 1)),
        ("attestations", List(Attestation, 1)),
        ("deposits", List(Deposit, 1)),
        ("voluntary_exits", List(VoluntaryExit, 1)),
    ]

    def __init__(
        self,
        *,
        randao_reveal: bytes96 = EMPTY_SIGNATURE,
        eth1_data: Eth1Data = default_eth1_data,
        graffiti: Hash32 = ZERO_HASH32,
        proposer_slashings: Sequence[ProposerSlashing] = default_tuple,
        attester_slashings: Sequence[AttesterSlashing] = default_tuple,
        attestations: Sequence[Attestation] = default_tuple,
        deposits: Sequence[Deposit] = default_tuple,
        voluntary_exits: Sequence[VoluntaryExit] = default_tuple,
    ) -> None:
        super().__init__(
            randao_reveal=randao_reveal,
            eth1_data=eth1_data,
            graffiti=graffiti,
            proposer_slashings=proposer_slashings,
            attester_slashings=attester_slashings,
            attestations=attestations,
            deposits=deposits,
            voluntary_exits=voluntary_exits,
        )

    @property
    def is_empty(self) -> bool:
        return self == BeaconBlockBody()

    def __str__(self) -> str:
        return (
            f"randao_reveal={humanize_hash(self.randao_reveal)},"
            f" graffiti={humanize_hash(self.graffiti)},"
            f" proposer_slashings={self.proposer_slashings},"
            f" attester_slashings={self.attester_slashings},"
            f" attestations={self.attestations},"
            f" deposits={self.deposits},"
            f" voluntary_exits={self.voluntary_exits},"
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {str(self)}>"


default_beacon_block_body = BeaconBlockBody()


class BaseBeaconBlock(ssz.SignedSerializable, Configurable, ABC):
    fields = [
        ("slot", uint64),
        ("parent_root", bytes32),
        ("state_root", bytes32),
        ("body", BeaconBlockBody),
        ("signature", bytes96),
    ]

    def __init__(
        self,
        *,
        slot: Slot = default_slot,
        parent_root: SigningRoot = ZERO_SIGNING_ROOT,
        state_root: Hash32 = ZERO_HASH32,
        body: BeaconBlockBody = default_beacon_block_body,
        signature: BLSSignature = EMPTY_SIGNATURE,
    ) -> None:
        super().__init__(
            slot=slot,
            parent_root=parent_root,
            state_root=state_root,
            body=body,
            signature=signature,
        )

    def __str__(self) -> str:
        return (
            f"[signing_root]={humanize_hash(self.signing_root)},"
            f" [hash_tree_root]={humanize_hash(self.hash_tree_root)},"
            f" slot={self.slot},"
            f" parent_root={humanize_hash(self.parent_root)},"
            f" state_root={humanize_hash(self.state_root)},"
            f" body=({self.body}),"
            f" signature={humanize_hash(self.signature)}"
        )

    @property
    def is_genesis(self) -> bool:
        return self.parent_root == GENESIS_PARENT_ROOT

    @property
    def header(self) -> BeaconBlockHeader:
        return BeaconBlockHeader(
            slot=self.slot,
            parent_root=self.parent_root,
            state_root=self.state_root,
            body_root=self.body.hash_tree_root,
            signature=self.signature,
        )

    @classmethod
    @abstractmethod
    def from_root(
        cls, root: SigningRoot, chaindb: "BaseBeaconChainDB"
    ) -> "BaseBeaconBlock":
        """
        Return the block denoted by the given block root.
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {str(self)}>"


class BeaconBlock(BaseBeaconBlock):
    block_body_class = BeaconBlockBody

    @classmethod
    def from_root(
        cls, root: SigningRoot, chaindb: "BaseBeaconChainDB"
    ) -> "BeaconBlock":
        """
        Return the block denoted by the given block ``root``.
        """
        block = chaindb.get_block_by_root(root, cls)
        body = cls.block_body_class(
            randao_reveal=block.body.randao_reveal,
            eth1_data=block.body.eth1_data,
            graffiti=block.body.graffiti,
            proposer_slashings=block.body.proposer_slashings,
            attester_slashings=block.body.attester_slashings,
            attestations=block.body.attestations,
            deposits=block.body.deposits,
            voluntary_exits=block.body.voluntary_exits,
        )

        return cls(
            slot=block.slot,
            parent_root=block.parent_root,
            state_root=block.state_root,
            body=body,
            signature=block.signature,
        )

    @classmethod
    def from_parent(
        cls, parent_block: "BaseBeaconBlock", block_params: FromBlockParams
    ) -> "BaseBeaconBlock":
        """
        Initialize a new block with the ``parent_block`` as the block's
        previous block root.
        """
        if block_params.slot is None:
            slot = parent_block.slot + 1
        else:
            slot = block_params.slot

        return cls(
            slot=slot,
            parent_root=parent_block.signing_root,
            state_root=parent_block.state_root,
            body=cls.block_body_class(),
        )

    @classmethod
    def convert_block(cls, block: "BaseBeaconBlock") -> "BeaconBlock":
        return cls(
            slot=block.slot,
            parent_root=block.parent_root,
            state_root=block.state_root,
            body=block.body,
            signature=block.signature,
        )

    @classmethod
    def from_header(cls, header: BeaconBlockHeader) -> "BeaconBlock":
        return cls(
            slot=header.slot,
            parent_root=header.parent_root,
            state_root=header.state_root,
            signature=header.signature,
            body=BeaconBlockBody(),
        )
