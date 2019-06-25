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
    ZERO_HASH32,
)
from eth2.beacon.typing import (
    Epoch,
)


def _round_down_to_previous_multiple(amount: int, increment: int) -> int:
    return amount - amount % increment


class Validator(ssz.Serializable):

    fields = [
        ('pubkey', bytes48),
        ('withdrawal_credentials', bytes32),
        ('effective_balance', uint64)
        ('slashed', boolean),
        # Epoch when validator became eligible for activation
        ('activation_eligibility_epoch', uint64),
        # Epoch when validator activated
        ('activation_epoch', uint64),
        # Epoch when validator exited
        ('exit_epoch', uint64),
        # Epoch when validator withdrew
        ('withdrawable_epoch', uint64),
    ]

    def __init__(self,
                 *,
                 pubkey: BLSPubkey=b'\x00' * 48,
                 withdrawal_credentials: Hash32=ZERO_HASH32,
                 effective_balance: uint64=0,
                 slashed: bool=False,
                 activation_eligibility_epoch: Epoch=0,
                 activation_epoch: Epoch=0,
                 exit_epoch: Epoch=0,
                 withdrawable_epoch: Epoch=0) -> None:
        super().__init__(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            effective_balance=effective_balance,
            slashed=slashed,
            activation_eligibility_epoch=activation_eligibility_epoch,
            activation_epoch=activation_epoch,
            exit_epoch=exit_epoch,
            withdrawable_epoch=withdrawable_epoch,
        )

    def is_active(self, epoch: Epoch) -> bool:
        """
        Return ``True`` if the validator is active during the epoch, ``epoch``.

        From `is_active_validator` in the spec.
        """
        return self.activation_epoch <= epoch < self.exit_epoch

    def is_slashable(self, epoch: Epoch) -> bool:
        """
        From `is_slashable_validator` in the spec.
        """
        not_slashed = self.slashed is False
        active_but_not_withdrawable = self.activation_epoch <= epoch < self.withdrawable_epoch
        return not_slashed and active_but_not_withdrawable

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
            effective_balance=min(
                _round_down_to_previous_multiple(
                    amount,
                    config.EFFECTIVE_BALANCE_INCREMENT,
                ),
                config.MAX_EFFECTIVE_BALANCE,
            ),
            activation_eligibility_epoch=FAR_FUTURE_EPOCH,
            activation_epoch=FAR_FUTURE_EPOCH,
            exit_epoch=FAR_FUTURE_EPOCH,
            withdrawable_epoch=FAR_FUTURE_EPOCH,
        )
