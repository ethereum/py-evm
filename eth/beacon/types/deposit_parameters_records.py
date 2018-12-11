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
    uint256,
)


class DepositParametersRecord(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # BLS pubkey
        ('pubkey', uint256),
        # BLS proof of possession (a BLS signature)
        ('proof_of_possession', CountableList(uint256)),
        # Withdrawal credentials
        ('withdrawal_credentials', hash32),
        # Initial RANDAO commitment
        ('randao_commitment', hash32),
    ]

    def __init__(self,
                 pubkey: int,
                 withdrawal_credentials: Hash32,
                 randao_commitment: Hash32,
                 proof_of_possession: Sequence[int]=None) -> None:
        if proof_of_possession is None:
            proof_of_possession = (0, 0)

        super().__init__(
            pubkey=pubkey,
            proof_of_possession=proof_of_possession,
            withdrawal_credentials=withdrawal_credentials,
            randao_commitment=randao_commitment,
        )
