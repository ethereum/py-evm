from typing import (
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
    bytes32,
    bytes96,
    uint64,
)

from eth2.beacon.constants import EMPTY_SIGNATURE
from eth2.beacon.typing import (
    Slot,
)


if TYPE_CHECKING:
    from eth2.beacon.db.chain import BaseBeaconChainDB  # noqa: F401


class BeaconBlockHeader(ssz.SignedSerializable):

    fields = [
        ('slot', uint64),
        ('previous_block_root', bytes32),
        ('state_root', bytes32),
        ('block_body_root', bytes32),
        ('signature', bytes96),
    ]

    def __init__(self,
                 *,
                 slot: Slot,
                 previous_block_root: Hash32,
                 state_root: Hash32,
                 block_body_root: Hash32,
                 signature: BLSSignature=EMPTY_SIGNATURE):
        super().__init__(
            slot=slot,
            previous_block_root=previous_block_root,
            state_root=state_root,
            block_body_root=block_body_root,
            signature=signature,
        )

    def __repr__(self) -> str:
        return (
            f'<Block #{self.slot} '
            f'signing_root={encode_hex(self.signing_root)[2:10]} '
            f'root={encode_hex(self.root)[2:10]}>'
        )
