from eth_typing import (
    Hash32,
)
import rlp
from rlp.sedes import (
    binary,
)

from eth2.beacon.sedes import (
    hash32,
)
from eth2.beacon._utils.hash import hash_eth2
from eth2.beacon.typing import (
    BLSPubkey,
    BLSSignature,
)
from eth2.beacon.constants import EMPTY_SIGNATURE


class DepositInput(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # BLS pubkey
        ('pubkey', binary),
        # Withdrawal credentials
        ('withdrawal_credentials', hash32),
        # BLS proof of possession (a BLS signature)
        ('proof_of_possession', binary),
    ]

    def __init__(self,
                 pubkey: BLSPubkey,
                 withdrawal_credentials: Hash32,
                 proof_of_possession: BLSSignature=EMPTY_SIGNATURE) -> None:
        super().__init__(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            proof_of_possession=proof_of_possession,
        )

    _root = None

    @property
    def root(self) -> Hash32:
        if self._root is None:
            self._root = hash_eth2(rlp.encode(self))
        return self._root
