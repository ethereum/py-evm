from eth_typing import (
    BLSSignature,
    Hash32,
)
import ssz
from ssz.sedes import (
    bytes96,
    uint64,
)

from eth2.beacon._utils.hash import (
    hash_eth2,
)
from eth2.beacon.typing import (
    Epoch,
    ValidatorIndex,
)
from eth2.beacon.constants import EMPTY_SIGNATURE


class VoluntaryExit(ssz.Serializable):

    fields = [
        # Minimum epoch for processing exit
        ('epoch', uint64),
        # Index of the exiting validator
        ('validator_index', uint64),
        # Validator signature
        ('signature', bytes96),
    ]

    def __init__(self,
                 epoch: Epoch,
                 validator_index: ValidatorIndex,
                 signature: BLSSignature=EMPTY_SIGNATURE) -> None:
        super().__init__(
            epoch,
            validator_index,
            signature,
        )

    _signed_root = None

    @property
    def signed_root(self) -> Hash32:
        # Use SSZ built-in function
        if self._signed_root is None:
            self._signed_root = hash_eth2(ssz.encode(self.copy(signature=EMPTY_SIGNATURE)))
        return self._signed_root
