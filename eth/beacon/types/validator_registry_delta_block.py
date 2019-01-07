from eth_typing import (
    Hash32,
)
import rlp

from eth.beacon._utils.hash import (
    hash_eth2,
)
from eth.beacon.typing import (
    BLSPubkey,
    SlotNumber,
    ValidatorIndex,
)

from eth.beacon.enums import (
    ValidatorRegistryDeltaFlag,
)

from eth.rlp.sedes import (
    hash32,
    uint24,
    uint64,
    uint384,
)


class ValidatorRegistryDeltaBlock(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        ('latest_registry_delta_root', hash32),
        ('validator_index', uint24),
        ('pubkey', uint384),
        ('slot', uint64),
        ('flag', uint64),
    ]

    def __init__(self,
                 latest_registry_delta_root: Hash32,
                 validator_index: ValidatorIndex,
                 pubkey: BLSPubkey,
                 slot: SlotNumber,
                 flag: ValidatorRegistryDeltaFlag) -> None:
        super().__init__(
            latest_registry_delta_root=latest_registry_delta_root,
            validator_index=validator_index,
            pubkey=pubkey,
            slot=slot,
            flag=flag,
        )

    _hash = None

    @property
    def hash(self) -> Hash32:
        if self._hash is None:
            self._hash = hash_eth2(rlp.encode(self))
        return self._hash

    @property
    def root(self) -> Hash32:
        # Alias of `hash`.
        # Using flat hash, might change to SSZ tree hash.
        return self.hash
