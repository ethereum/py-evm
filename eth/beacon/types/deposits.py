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
    uint256,
)


class DepositParameters(rlp.Serializable):
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
            deposit_parameters=deposit_parameters,
            value=value,
            timestamp=timestamp,
        )


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
            merkle_branch=merkle_branch,
            merkle_tree_index=merkle_tree_index,
            deposit_data=deposit_data,
        )
