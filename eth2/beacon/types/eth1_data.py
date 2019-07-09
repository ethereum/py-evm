from eth_typing import (
    Hash32,
)

import ssz
from ssz.sedes import (
    bytes32,
    uint64,
)

from eth.constants import (
    ZERO_HASH32,
)


class Eth1Data(ssz.Serializable):

    fields = [
        ('deposit_root', bytes32),
        ('deposit_count', uint64),
        ('block_hash', bytes32),
    ]

    def __init__(self,
                 deposit_root: Hash32=ZERO_HASH32,
                 deposit_count: int=0,
                 block_hash: Hash32=ZERO_HASH32) -> None:
        super().__init__(
            deposit_root=deposit_root,
            deposit_count=deposit_count,
            block_hash=block_hash,
        )


default_eth1_data = Eth1Data()
