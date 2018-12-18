from eth_typing import (
    Hash32,
)
import rlp

from eth.beacon.enums import (
    ValidatorStatusCode,
)
from eth.rlp.sedes import (
    uint64,
    uint384,
    hash32,
)


VALIDATOR_RECORD_ACTIVE_STATUSES = {
    ValidatorStatusCode.ACTIVE,
    ValidatorStatusCode.ACTIVE_PENDING_EXIT,
}


class ValidatorRecord(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # BLS public key
        ('pubkey', uint384),
        # Withdrawal credentials
        ('withdrawal_credentials', hash32),
        # RANDAO commitment
        ('randao_commitment', hash32),
        # Slot the proposer has skipped (ie. layers of RANDAO expected)
        ('randao_layers', uint64),
        # Balance in Gwei
        ('balance', uint64),
        # Status code
        ('status', uint64),
        # Slot when validator last changed status (or 0)
        ('latest_status_change_slot', uint64),
        # Sequence number when validator exited (or 0)
        ('exit_count', uint64),
    ]

    def __init__(self,
                 pubkey: int,
                 withdrawal_credentials: Hash32,
                 randao_commitment: Hash32,
                 randao_layers: int,
                 balance: int,
                 status: int,
                 latest_status_change_slot: int,
                 exit_count: int) -> None:
        super().__init__(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            randao_commitment=randao_commitment,
            randao_layers=randao_layers,
            balance=balance,
            status=status,
            latest_status_change_slot=latest_status_change_slot,
            exit_count=exit_count,
        )

    @property
    def is_active(self) -> bool:
        """
        Returns ``True`` if the validator is active.
        """
        return self.status in VALIDATOR_RECORD_ACTIVE_STATUSES
