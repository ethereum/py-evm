from eth_typing import (
    Address,
    Hash32,
)
import rlp

from eth.rlp.sedes import (
    address,
    uint8,
    uint16,
    uint64,
    uint256,
    hash32,
)


class ValidatorRecord(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # BLS public key
        ('pubkey', uint256),
        # Withdrawal shard number
        ('withdrawal_shard', uint16),
        # Withdrawal address
        ('withdrawal_address', address),
        # RANDAO commitment
        ('randao_commitment', hash32),
        # Slot the RANDAO commitment was last changed
        ('randao_last_change', uint64),
        # Balance in Gwei
        ('balance', uint64),
        # Status code
        ('status', uint8),
        # Slot when validator exited (or 0)
        ('exit_slot', uint64),
        # Sequence number when validator exited (or 0)
        ('exit_seq', uint64),
    ]

    def __init__(self,
                 pubkey: int,
                 withdrawal_shard: int,
                 withdrawal_address: Address,
                 randao_commitment: Hash32,
                 randao_last_change: int,
                 balance: int,
                 status: int,
                 exit_slot: int,
                 exit_seq: int) -> None:
        super().__init__(
            pubkey=pubkey,
            withdrawal_shard=withdrawal_shard,
            withdrawal_address=withdrawal_address,
            randao_commitment=randao_commitment,
            randao_last_change=randao_last_change,
            balance=balance,
            status=status,
            exit_slot=exit_slot,
            exit_seq=exit_seq,
        )
