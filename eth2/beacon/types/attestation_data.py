from eth_utils import humanize_hash
import ssz
from ssz.sedes import bytes32, uint64

from eth2.beacon.constants import ZERO_SIGNING_ROOT
from eth2.beacon.types.checkpoints import Checkpoint, default_checkpoint
from eth2.beacon.types.defaults import default_committee_index, default_slot
from eth2.beacon.typing import CommitteeIndex, SigningRoot, Slot


class AttestationData(ssz.Serializable):

    fields = [
        ("slot", uint64),
        ("index", uint64),
        # LMD GHOST vote
        ("beacon_block_root", bytes32),
        # FFG vote
        ("source", Checkpoint),
        ("target", Checkpoint),
    ]

    def __init__(
        self,
        slot: Slot = default_slot,
        index: CommitteeIndex = default_committee_index,
        beacon_block_root: SigningRoot = ZERO_SIGNING_ROOT,
        source: Checkpoint = default_checkpoint,
        target: Checkpoint = default_checkpoint,
    ) -> None:
        super().__init__(
            slot=slot,
            index=index,
            beacon_block_root=beacon_block_root,
            source=source,
            target=target,
        )

    def __str__(self) -> str:
        return (
            f"slot={self.slot},"
            f" index={self.index},"
            f" beacon_block_root={humanize_hash(self.beacon_block_root)},"
            f" source=({self.source}),"
            f" target=({self.target}),"
        )


default_attestation_data = AttestationData()
