
import rlp
from eth.rlp.sedes import uint64
from .deposit_parameters import DepositParameters

class DepositData(rlp.Serializable):
    """
    Not in spec, this is for fields in Deposit
    """
    fields = [
        # Deposit parameters
        ('deposit_parameters', DepositParameters),
        # Value in Gwei
        ('value', uint64),
        # Timestamp from deposit contract
        ('timestamp', uint64),
    ]

    def __init__(self,
                 deposit_parameters: DepositParameters,
                 value: int,
                 timestamp: int) -> None:

        super().__init__(
            deposit_parameters,
            value,
            timestamp,
        )