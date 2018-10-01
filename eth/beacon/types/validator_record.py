from eth_typing import (
    Address,
    Hash32,
)
import rlp

from eth.rlp.sedes import (
    address,
    int16,
    int64,
    int128,
    int256,
    hash32,
)


class ValidatorRecord(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # The validator's public key
        ('pubkey', int256),
        # What shard the validator's balance will be sent to after withdrawal
        ('withdrawal_shard', int16),
        # And what address
        ('withdrawal_address', address),
        # The validator's current RANDAO beacon commitment
        ('randao_commitment', hash32),
        # Current balance
        ('balance', int128),
        # Dynasty where the validator is inducted
        ('start_dynasty', int64),
        # Dynasty where the validator leaves
        ('end_dynasty', int64),
    ]

    def __init__(self,
                 pubkey: int,
                 withdrawal_shard: int,
                 withdrawal_address: Address,
                 randao_commitment: Hash32,
                 balance: int,
                 start_dynasty: int,
                 end_dynasty: int) -> None:
        super().__init__(
            pubkey=pubkey,
            withdrawal_shard=withdrawal_shard,
            withdrawal_address=withdrawal_address,
            randao_commitment=randao_commitment,
            balance=balance,
            start_dynasty=start_dynasty,
            end_dynasty=end_dynasty,
        )
