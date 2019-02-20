from eth_typing import (
    Hash32,
)
import ssz
from ssz.sedes import (
    bytes32,
    bytes48,
    uint64,
)

from eth2.beacon.constants import (
    FAR_FUTURE_EPOCH,
)
from eth2.beacon.typing import (
    BLSPubkey,
    EpochNumber,
)


class ValidatorRecord(ssz.Serializable):

    fields = [
        # BLS public key
        ('pubkey', bytes48),
        # Withdrawal credentials
        ('withdrawal_credentials', bytes32),
        # Epoch when validator activated
        ('activation_epoch', uint64),
        # Epoch when validator exited
        ('exit_epoch', uint64),
        # Epoch when validator withdrew
        ('withdrawal_epoch', uint64),
        # Epoch when validator was penalized
        ('slashed_epoch', uint64),
        # Status flags
        ('status_flags', uint64),
    ]

    def __init__(self,
                 pubkey: BLSPubkey,
                 withdrawal_credentials: Hash32,
                 activation_epoch: EpochNumber,
                 exit_epoch: EpochNumber,
                 withdrawal_epoch: EpochNumber,
                 slashed_epoch: EpochNumber,
                 status_flags: int) -> None:
        super().__init__(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            activation_epoch=activation_epoch,
            exit_epoch=exit_epoch,
            withdrawal_epoch=withdrawal_epoch,
            slashed_epoch=slashed_epoch,
            status_flags=status_flags,
        )

    def is_active(self, epoch: EpochNumber) -> bool:
        """
        Return ``True`` if the validator is active during the epoch, ``epoch``.
        """
        return self.activation_epoch <= epoch < self.exit_epoch

    @classmethod
    def create_pending_validator(cls,
                                 pubkey: BLSPubkey,
                                 withdrawal_credentials: Hash32) -> 'ValidatorRecord':
        """
        Return a new pending ``ValidatorRecord`` with the given fields.
        """
        return cls(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            activation_epoch=FAR_FUTURE_EPOCH,
            exit_epoch=FAR_FUTURE_EPOCH,
            withdrawal_epoch=FAR_FUTURE_EPOCH,
            slashed_epoch=FAR_FUTURE_EPOCH,
            status_flags=0,
        )
