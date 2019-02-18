import ssz
from ssz.sedes import (
    uint64,
)

from .deposit_input import DepositInput
from eth2.beacon.typing import (
    Timestamp,
    Gwei,
)


class DepositData(ssz.Serializable):
    """
    :class:`~eth2.beacon.types.deposit_data.DepositData` corresponds to the data broadcast from the
    Ethereum 1.0 deposit contract after a successful call to the ``deposit`` function on that
    contract.
    """
    fields = [
        # Amount in Gwei
        ('amount', uint64),
        # Timestamp from deposit contract
        ('timestamp', uint64),
        # Deposit input
        ('deposit_input', DepositInput),
    ]

    def __init__(self,
                 amount: Gwei,
                 timestamp: Timestamp,
                 deposit_input: DepositInput) -> None:

        super().__init__(
            amount,
            timestamp,
            deposit_input,
        )
