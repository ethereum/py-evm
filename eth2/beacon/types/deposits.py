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
    A :class:`~eth2.beacon.types.deposits.Deposit` contains the data represented by an instance
    of :class:`~eth2.beacon.types.deposit_data.DepositData`, along with a Merkle proof (``branch``
    and ``index``) that can be used to verify inclusion in the canonical deposit tree.

    .. note:: using RLP until we have standardized serialization format.
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
                 branch: Sequence[Hash32],
                 index: int,
                 deposit_data: DepositData)-> None:
        super().__init__(
            branch,
            index,
            deposit_data,
        )
