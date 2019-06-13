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
        # Ethereum 1.0 chain block hash
        ('block_hash', bytes32),
        # Root of the deposit tree
        ('deposit_root', bytes32),
        # Total number of deposits
        ('deposit_count', uint64)
    ]

    def __init__(self,
                 block_hash: Hash32=ZERO_HASH32,
                 deposit_root: Hash32=ZERO_HASH32,
                 deposit_count=0) -> None:
        super().__init__(
            block_hash=block_hash,
            deposit_root=deposit_root,
            deposit_count=deposit_count,
        )
