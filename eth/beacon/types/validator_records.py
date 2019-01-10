from eth_typing import (
    Hash32,
)
import rlp

from eth.rlp.sedes import (
    uint64,
    uint384,
    hash32,
)
from eth.beacon.constants import (
    FAR_FUTURE_SLOT,
)
from eth.beacon.typing import (
    SlotNumber,
    BLSPubkey,
)


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
        # Slot when validator activated
        ('activation_slot', uint64),
        # Slot when validator exited
        ('exit_slot', uint64),
        # Slot when validator withdrew
        ('withdrawal_slot', uint64),
        # Slot when validator was penalized
        ('penalized_slot', uint64),
        # Exit counter when validator exited
        ('exit_count', uint64),
        # Status flags
        ('status_flags', uint64),
        # Proof of custody commitment
        ('custody_commitment', hash32),
        # Slot of latest custody reseed
        ('latest_custody_reseed_slot', uint64),
        # Slot of second-latest custody reseed
        ('penultimate_custody_reseed_slot', uint64),
    ]

    def __init__(self,
                 pubkey: BLSPubkey,
                 withdrawal_credentials: Hash32,
                 randao_commitment: Hash32,
                 randao_layers: int,
                 activation_slot: SlotNumber,
                 exit_slot: SlotNumber,
                 withdrawal_slot: SlotNumber,
                 penalized_slot: SlotNumber,
                 exit_count: int,
                 status_flags: int,
                 custody_commitment: Hash32,
                 latest_custody_reseed_slot: SlotNumber,
                 penultimate_custody_reseed_slot: SlotNumber) -> None:
        super().__init__(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            randao_commitment=randao_commitment,
            randao_layers=randao_layers,
            activation_slot=activation_slot,
            exit_slot=exit_slot,
            withdrawal_slot=withdrawal_slot,
            penalized_slot=penalized_slot,
            exit_count=exit_count,
            status_flags=status_flags,
            custody_commitment=custody_commitment,
            latest_custody_reseed_slot=latest_custody_reseed_slot,
            penultimate_custody_reseed_slot=penultimate_custody_reseed_slot,
        )

    def is_active(self, slot: int) -> bool:
        """
        Return ``True`` if the validator is active during the slot, ``slot``.
        """
        return self.activation_slot <= slot < self.exit_slot

    @classmethod
    def create_pending_validator(cls,
                                 pubkey: BLSPubkey,
                                 withdrawal_credentials: Hash32,
                                 randao_commitment: Hash32,
                                 custody_commitment: Hash32) -> 'ValidatorRecord':
        """
        Return a new pending ``ValidatorRecord`` with the given fields.
        """
        return cls(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            randao_commitment=randao_commitment,
            randao_layers=0,
            activation_slot=FAR_FUTURE_SLOT,
            exit_slot=FAR_FUTURE_SLOT,
            withdrawal_slot=FAR_FUTURE_SLOT,
            penalized_slot=FAR_FUTURE_SLOT,
            exit_count=0,
            status_flags=0,
            custody_commitment=custody_commitment,
            latest_custody_reseed_slot=SlotNumber(0),
            penultimate_custody_reseed_slot=SlotNumber(0),
        )
