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

from eth2.configs import Eth2Config
from eth2.beacon.constants import (
    FAR_FUTURE_EPOCH,
)
from eth2.beacon.typing import (
    Epoch,
)


def _round_down_to_previous_multiple(amount: int, increment: int) -> int:
    return amount - amount % increment


class Validator(ssz.Serializable):

    fields = [
        # BLS public key
        ('pubkey', bytes48),
        # Withdrawal credentials
        ('withdrawal_credentials', bytes32),
        # Epoch when validator became eligible for activation
        ('activation_eligibility_epoch', uint64),
        # Epoch when validator activated
        ('activation_epoch', uint64),
        # Epoch when validator exited
        ('exit_epoch', uint64),
        # Epoch when validator withdrew
        ('withdrawable_epoch', uint64),
        # Was the validator slashed
        ('slashed', boolean),
        # Effective balance
        ('effective_balance', uint64)
    ]

    def __init__(self,
                 pubkey: BLSPubkey,
                 withdrawal_credentials: Hash32,
                 activation_eligibility_epoch: Epoch,
                 activation_epoch: Epoch,
                 exit_epoch: Epoch,
                 withdrawable_epoch: Epoch,
                 slashed: bool,
                 effective_balance: uint64) -> None:
        super().__init__(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            activation_eligibility_epoch=activation_eligibility_epoch,
            activation_epoch=activation_epoch,
            exit_epoch=exit_epoch,
            withdrawable_epoch=withdrawable_epoch,
            slashed=slashed,
            effective_balance=effective_balance,
        )

    def is_active(self, epoch: Epoch) -> bool:
        """
        Return ``True`` if the validator is active during the epoch, ``epoch``.
        """
        return self.activation_epoch <= epoch < self.exit_epoch

    @classmethod
    def create_pending_validator(cls,
                                 pubkey: BLSPubkey,
                                 withdrawal_credentials: Hash32,
                                 amount: int,
                                 config: Eth2Config) -> 'Validator':
        """
        Return a new pending ``Validator`` with the given fields.
        """
        return cls(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            activation_eligibility_epoch=FAR_FUTURE_EPOCH,
            activation_epoch=FAR_FUTURE_EPOCH,
            exit_epoch=FAR_FUTURE_EPOCH,
            withdrawable_epoch=FAR_FUTURE_EPOCH,
            slashed=False,
            effective_balance=min(
                _round_down_to_previous_multiple(
                    amount,
                    config.EFFECTIVE_BALANCE_INCREMENT,
                ),
                config.MAX_EFFECTIVE_BALANCE,
            ),
        )
