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


class DepositInput(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # BLS pubkey
        ('pubkey', uint384),
        # BLS proof of possession (a BLS signature)
        ('proof_of_possession', CountableList(uint384)),
        # Withdrawal credentials
        ('withdrawal_credentials', hash32),
        # Initial RANDAO commitment
        ('randao_commitment', hash32),
    ]

    def __init__(self,
                 pubkey: int,
                 withdrawal_credentials: Hash32,
                 randao_commitment: Hash32,
                 proof_of_possession: Sequence[int]=(0, 0)) -> None:
        super().__init__(
            pubkey,
            proof_of_possession,
            withdrawal_credentials,
            randao_commitment,
        )
