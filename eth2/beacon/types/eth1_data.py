from eth_typing import (
    Hash32,
)

import ssz
from ssz.sedes import (
    bytes32,
)

from eth.constants import (
    ZERO_HASH32,
)


class Eth1Data(ssz.Serializable):

    fields = [
        # Root of the deposit tree
        ('deposit_root', bytes32),
        # Ethereum 1.0 chain block hash
        ('block_hash', bytes32),
    ]

    def __init__(self,
                 deposit_root: Hash32,
                 block_hash: Hash32) -> None:
        super().__init__(
            deposit_root=deposit_root,
            block_hash=block_hash,
        )

    @classmethod
    def create_empty_data(cls) -> 'Eth1Data':
        return cls(
            deposit_root=ZERO_HASH32,
            block_hash=ZERO_HASH32,
        )
