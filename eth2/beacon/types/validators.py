from eth_typing import (
    BLSPubkey,
    Hash32,
)
import ssz
from ssz.sedes import (
    boolean,
    bytes32,
    bytes48,
    uint64,
)

from eth2.beacon.constants import (
    FAR_FUTURE_EPOCH,
)
from eth2.beacon.typing import (
    Epoch,
)


class Validator(ssz.Serializable):

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
        ('withdrawable_epoch', uint64),
        # Did the validator initiate an exit
        ('initiated_exit', boolean),
        # Was the validator slashed
        ('slashed', boolean),
    ]

    def __init__(self,
                 pubkey: BLSPubkey,
                 withdrawal_credentials: Hash32,
                 activation_epoch: Epoch,
                 exit_epoch: Epoch,
                 withdrawable_epoch: Epoch,
                 initiated_exit: bool,
                 slashed: bool) -> None:
        super().__init__(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            activation_epoch=activation_epoch,
            exit_epoch=exit_epoch,
            withdrawable_epoch=withdrawable_epoch,
            initiated_exit=initiated_exit,
            slashed=slashed,
        )

    def is_active(self, epoch: Epoch) -> bool:
        """
        Return ``True`` if the validator is active during the epoch, ``epoch``.
        """
        return self.activation_epoch <= epoch < self.exit_epoch

    @classmethod
    def create_pending_validator(cls,
                                 pubkey: BLSPubkey,
                                 withdrawal_credentials: Hash32) -> 'Validator':
        """
        Return a new pending ``Validator`` with the given fields.
        """
        return cls(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            activation_epoch=FAR_FUTURE_EPOCH,
            exit_epoch=FAR_FUTURE_EPOCH,
            withdrawable_epoch=FAR_FUTURE_EPOCH,
            initiated_exit=False,
            slashed=False,
        )
