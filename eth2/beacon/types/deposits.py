from typing import (
    Sequence,
)

from eth.constants import (
    ZERO_HASH32,
)
from eth_utils import (
    encode_hex,
)
from eth_typing import (
    Hash32,
)
import ssz
from ssz.sedes import (
    Vector,
    bytes32,
)

from eth2.beacon.constants import (
    DEPOSIT_CONTRACT_TREE_DEPTH,
)

from .deposit_data import (
    DepositData,
    default_deposit_data,
)

from .defaults import (
    default_tuple_of_size,
)

default_proof_tuple = default_tuple_of_size(DEPOSIT_CONTRACT_TREE_DEPTH, ZERO_HASH32)


class Deposit(ssz.Serializable):
    """
    A :class:`~eth2.beacon.types.deposits.Deposit` contains the data represented by an instance
    of :class:`~eth2.beacon.types.deposit_data.DepositData`, along with a Merkle proof that can be
    used to verify inclusion in the canonical deposit tree.
    """

    fields = [
        # Merkle path to deposit root
        ('proof', Vector(bytes32, DEPOSIT_CONTRACT_TREE_DEPTH)),
        ('data', DepositData),
    ]

    def __init__(self,
                 proof: Sequence[Hash32]=default_proof_tuple,
                 data: DepositData=default_deposit_data)-> None:
        super().__init__(
            proof,
            data,
        )

    def __repr__(self) -> str:
        return f"<Deposit root: {encode_hex(self.root)[0:8]} data: {self.data}>"
