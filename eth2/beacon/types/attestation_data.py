from eth.constants import (
    ZERO_HASH32,
)

from eth_typing import (
    Hash32,
)

import ssz
from ssz.sedes import (
    uint64,
    bytes32,
)

from eth2.beacon.typing import (
    Epoch,
)
from eth2.beacon.types.crosslinks import (
    Crosslink,
    default_crosslink,
)
from eth_utils import (
    humanize_hash,
)

from .defaults import (
    default_epoch,
)


class AttestationData(ssz.Serializable):

    fields = [
        # LMD GHOST vote
        ('beacon_block_root', bytes32),

        # FFG vote
        ('source_epoch', uint64),
        ('source_root', bytes32),
        ('target_epoch', uint64),
        ('target_root', bytes32),

        # Crosslink vote
        ('crosslink', Crosslink),
    ]

    def __init__(self,
                 beacon_block_root: Hash32=ZERO_HASH32,
                 source_epoch: Epoch=default_epoch,
                 source_root: Hash32=ZERO_HASH32,
                 target_epoch: Epoch=default_epoch,
                 target_root: Hash32=ZERO_HASH32,
                 crosslink: Crosslink=default_crosslink) -> None:
        super().__init__(
            beacon_block_root=beacon_block_root,
            source_epoch=source_epoch,
            source_root=source_root,
            target_epoch=target_epoch,
            target_root=target_root,
            crosslink=crosslink,
        )

    def __str__(self) -> str:
        return (
            f"beacon_block_root={humanize_hash(self.beacon_block_root)[2:10]}"
            f" source_epoch={self.source_epoch}"
            f" target_epoch={self.target_epoch}"
            f" | CL={self.crosslink}"
        )


default_attestation_data = AttestationData()
