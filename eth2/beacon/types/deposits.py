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
)

from .deposit_data import DepositData


class Deposit(ssz.Serializable):
    """
    A :class:`~eth2.beacon.types.deposits.Deposit` contains the data represented by an instance
    of :class:`~eth2.beacon.types.deposit_data.DepositData`, along with a Merkle proof that can be
    used to verify inclusion in the canonical deposit tree.
    """

    fields = [
        # Merkle branch in the deposit tree
        ('proof', Vector(bytes32, 1)),
        # Deposit data
        ('data', DepositData),
    ]

    def __init__(self,
                 proof: Sequence[Hash32]=tuple(),
                 deposit_data: DepositData=DepositData())-> None:
        super().__init__(
            proof,
            deposit_data,
        )
