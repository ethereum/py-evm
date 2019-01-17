import rlp
from eth2.beacon.sedes import uint64
from .deposit_input import DepositInput
from eth2.beacon.typing import (
    Timestamp,
    Gwei,
)


class DepositData(rlp.Serializable):
    """
    ``DepositData`` corresponds to the data broadcast from the Ethereum 1.0 deposit
    contract after a successful call to the `deposit` function.

    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        ('deposit_input', DepositInput),
        # Amount in Gwei
        ('amount', uint64),
        # Timestamp from deposit contract
        ('timestamp', uint64),
    ]

    def __init__(self,
                 deposit_input: DepositInput,
                 amount: Gwei,
                 timestamp: Timestamp) -> None:

        super().__init__(
            deposit_input,
            amount,
            timestamp,
        )
