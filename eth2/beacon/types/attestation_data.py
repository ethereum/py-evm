from eth.constants import ZERO_HASH32
from eth_typing import Hash32
from eth_utils import humanize_hash
import ssz
from ssz.sedes import bytes32

from eth2.beacon.types.checkpoints import Checkpoint, default_checkpoint
from eth2.beacon.types.crosslinks import Crosslink, default_crosslink


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
        beacon_block_root: Hash32 = ZERO_HASH32,
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
            f"beacon_block_root={humanize_hash(self.beacon_block_root)[2:10]}"
            f" source={self.source}"
            f" target={self.target}"
            f" | CL={self.crosslink}"
        )


default_attestation_data = AttestationData()
