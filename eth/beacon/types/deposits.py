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
    uint64,
)

from .deposit_data import DepositData


class Deposit(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """

    fields = [
        # Receipt Merkle branch
        ('merkle_branch', CountableList(hash32)),
        # Merkle tree index
        ('merkle_tree_index', uint64),
        # Deposit data
        ('deposit_data', DepositData),
    ]

    def __init__(self,
                 merkle_branch: Sequence[Hash32],
                 merkle_tree_index: int,
                 deposit_data: DepositData)-> None:
        super().__init__(
            merkle_branch,
            merkle_tree_index,
            deposit_data,
        )
