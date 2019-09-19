from eth_utils import humanize_hash
import ssz
from ssz.sedes import bytes32

from eth2.beacon.constants import ZERO_SIGNING_ROOT
from eth2.beacon.types.checkpoints import Checkpoint, default_checkpoint
from eth2.beacon.types.crosslinks import Crosslink, default_crosslink
from eth2.beacon.typing import SigningRoot


class AttestationData(ssz.Serializable):

    fields = [
        # LMD GHOST vote
        ("beacon_block_root", bytes32),
        # FFG vote
        ("source", Checkpoint),
        ("target", Checkpoint),
        # Crosslink vote
        ("crosslink", Crosslink),
    ]

    def __init__(
        self,
        beacon_block_root: SigningRoot = ZERO_SIGNING_ROOT,
        source: Checkpoint = default_checkpoint,
        target: Checkpoint = default_checkpoint,
        crosslink: Crosslink = default_crosslink,
    ) -> None:
        super().__init__(
            beacon_block_root=beacon_block_root,
            source=source,
            target=target,
            crosslink=crosslink,
        )

    def __str__(self) -> str:
        return (
            f"beacon_block_root={humanize_hash(self.beacon_block_root)},"
            f" source=({self.source}),"
            f" target=({self.target}),"
            f" crosslink=({self.crosslink})"
        )


default_attestation_data = AttestationData()
