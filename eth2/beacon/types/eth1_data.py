from eth_typing import (
    Hash32,
)
import rlp

from eth.constants import (
    ZERO_HASH32,
)
from eth2.beacon.sedes import (
    hash32,
)


class Eth1Data(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Root of the deposit tree
        ('deposit_root', hash32),
        # Ethereum 1.0 chain block hash
        ('block_hash', hash32),
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
