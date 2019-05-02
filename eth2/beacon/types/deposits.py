from typing import (
    Sequence,
)

from eth_typing import (
    Hash32,
)
import ssz
from ssz.sedes import (
    Vector,
    bytes32,
    uint64,
)

from .deposit_data import DepositData


class Deposit(ssz.Serializable):
    """
    A :class:`~eth2.beacon.types.deposits.Deposit` contains the data represented by an instance
    of :class:`~eth2.beacon.types.deposit_data.DepositData`, along with a Merkle proof (``branch``
    and ``index``) that can be used to verify inclusion in the canonical deposit tree.
    """

    fields = [
        # Merkle branch in the deposit tree
        ('proof', Vector(bytes32, 1)),
        # Index in the deposit tree
        ('index', uint64),
        # Deposit data
        ('deposit_data', DepositData),
    ]

    def __init__(self,
                 proof: Sequence[Hash32],
                 index: int,
                 deposit_data: DepositData)-> None:
        super().__init__(
            proof,
            index,
            deposit_data,
        )
