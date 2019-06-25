from eth_typing import (
    Hash32,
)

import ssz
from ssz.sedes import (
    uint64,
    bytes32,
)

from eth2.beacon.constants import (
    ZERO_HASH32,
)
from eth2.beacon.typing import (
    Epoch,
    Shard,
)
from eth_utils import (
    encode_hex,
    humanize_hash,
)

from .defaults import (
    default_shard,
    default_epoch,
)


class Crosslink(ssz.Serializable):

    fields = [
        ('shard', uint64),
        ('parent_root', bytes32),
        # Crosslinking data from epochs [start....end-1]
        ('start_epoch', uint64),
        ('end_epoch', uint64),
        # Root of the crosslinked shard data since the previous crosslink
        ('data_root', bytes32),
    ]

    def __init__(self,
                 shard: Shard=default_shard,
                 parent_root: Hash32=ZERO_HASH32,
                 start_epoch: Epoch=default_epoch,
                 end_epoch: Epoch=default_epoch,
                 data_root: Hash32=ZERO_HASH32) -> None:
        super().__init__(
            shard=shard,
            parent_root=parent_root,
            start_epoch=start_epoch,
            end_epoch=end_epoch,
            data_root=data_root,
        )

    def __str__(self) -> str:
        return (
            f"<Crosslink shard={self.shard}"
            f" start_epoch={self.start_epoch} end_epoch={self.end_epoch}"
            f" parent_root={humanize_hash(self.parent_root)}"
            f" data_root={humanize_hash(self.data_root)}>"
        )

    def __repr__(self) -> str:
        return (
            f"<Crosslink shard={self.shard}"
            f" start_epoch={self.start_epoch} end_epoch={self.end_epoch}"
            f" parent_root={encode_hex(self.parent_root)} data_root={encode_hex(self.data_root)}>"
        )


default_crosslink = Crosslink()
