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

from eth2.beacon.sedes import (
    hash32,
    uint64,
)

from .deposit_data import DepositData


class Deposit(rlp.Serializable):
    """
    A ``Deposit`` contains the data represented by an instance of ``DepositData``,
    along with a Merkle proof (``branch`` and ``index``) that can be used to verify
    inclusion in the canonical deposit tree.

    Note: using RLP until we have standardized serialization format.
    """

    fields = [
        # Merkle branch in the deposit tree
        ('branch', CountableList(hash32)),
        # Index in the deposit tree
        ('index', uint64),
        # Deposit data
        ('deposit_data', DepositData),
    ]

    def __init__(self,
                 merkle_branch: Sequence[Hash32],
                 merkle_tree_index: int,
                 deposit_data: DepositData)-> None:
        super().__init__(
            branch=merkle_branch,
            index=merkle_tree_index,
            deposit_data=deposit_data,
        )
