from eth.constants import (
    ZERO_HASH32,
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

from .defaults import (
    default_slot,
)


class BeaconBlockHeader(ssz.SignedSerializable):

    fields = [
        ('slot', uint64),
        ('parent_root', bytes32),
        ('state_root', bytes32),
        ('body_root', bytes32),
        ('signature', bytes96),
    ]

    def __init__(self,
                 *,
                 slot: Slot=default_slot,
                 parent_root: Hash32=ZERO_HASH32,
                 state_root: Hash32=ZERO_HASH32,
                 body_root: Hash32=ZERO_HASH32,
                 signature: BLSSignature=EMPTY_SIGNATURE):
        super().__init__(
            slot=slot,
            parent_root=parent_root,
            state_root=state_root,
            body_root=body_root,
            signature=signature,
        )

    def __repr__(self) -> str:
        return (
            f'<Block #{self.slot} '
            f'signing_root={encode_hex(self.signing_root)[2:10]} '
            f'root={encode_hex(self.root)[2:10]}>'
        )


default_beacon_block_header = BeaconBlockHeader()
