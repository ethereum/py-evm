from eth_typing import (
    Hash32,
)
import rlp

from eth.rlp.sedes import (
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
        # Withdrawal credentials
        ('withdrawal_credentials', hash32),
        # RANDAO commitment
        ('randao_commitment', hash32),
        # Slot the RANDAO commitment was last changed
        ('randao_last_change', uint64),
        # Balance in Gwei
        ('balance', uint64),
        # Status code
        ('status', uint64),
        # Slot when validator last changed status (or 0)
        ('last_status_change_slot', uint64),
        # Sequence number when validator exited (or 0)
        ('exit_seq', uint64),
    ]

    def __init__(self,
                 pubkey: int,
                 withdrawal_credentials: Hash32,
                 randao_commitment: Hash32,
                 randao_last_change: int,
                 balance: int,
                 status: int,
                 last_status_change_slot: int,
                 exit_seq: int) -> None:
        super().__init__(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            randao_commitment=randao_commitment,
            randao_last_change=randao_last_change,
            balance=balance,
            status=status,
            last_status_change_slot=last_status_change_slot,
            exit_seq=exit_seq,
        )
