from typing import (
    Sequence,
)

from eth_typing import (
    Hash32,
)
import rlp
from rlp.sedes import (
    CountableList,
)

from eth.rlp.sedes import (
    hash32,
    uint384,
)
from eth.beacon._utils.hash import hash_eth2
from eth.beacon.typing import (
    BLSPubkey,
    BLSSignatureAggregated,
)
from eth.beacon.constants import EMPTY_SIGNATURE

class DepositInput(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # BLS pubkey
        ('pubkey', uint384),
        # Withdrawal credentials
        ('withdrawal_credentials', hash32),
        # Initial RANDAO commitment
        ('randao_commitment', hash32),
        # BLS proof of possession (a BLS signature)
        ('proof_of_possession', CountableList(uint384)),
    ]

    def __init__(self,
                 pubkey: BLSPubkey,
                 withdrawal_credentials: Hash32,
                 randao_commitment: Hash32,
                 proof_of_possession: BLSSignatureAggregated=EMPTY_SIGNATURE) -> None:
        super().__init__(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            randao_commitment=randao_commitment,
            proof_of_possession=proof_of_possession,
        )

    _root = None

    @property
    def root(self) -> Hash32:
        if self._root is None:
            self._root = hash_eth2(rlp.encode(self))
        return self._root
