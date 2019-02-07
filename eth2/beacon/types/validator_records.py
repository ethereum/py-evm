from eth_typing import (
    Hash32,
)
import rlp
from rlp.sedes import (
    binary,
)

from eth2.beacon.sedes import (
    uint64,
    hash32,
)
from eth2.beacon.constants import (
    FAR_FUTURE_EPOCH,
)
from eth2.beacon.typing import (
    BLSPubkey,
    EpochNumber,
)


class ValidatorRecord(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # BLS public key
        ('pubkey', binary),
        # Withdrawal credentials
        ('withdrawal_credentials', hash32),
        # RANDAO commitment
        ('randao_commitment', hash32),
        # Slot the proposer has skipped (ie. layers of RANDAO expected)
        ('randao_layers', uint64),
        # Epoch when validator activated
        ('activation_epoch', uint64),
        # Epoch when validator exited
        ('exit_epoch', uint64),
        # Epoch when validator withdrew
        ('withdrawal_epoch', uint64),
        # Epoch when validator was penalized
        ('penalized_epoch', uint64),
        # Exit counter when validator exited
        ('exit_count', uint64),
        # Status flags
        ('status_flags', uint64),
    ]

    def __init__(self,
                 pubkey: BLSPubkey,
                 withdrawal_credentials: Hash32,
                 randao_commitment: Hash32,
                 randao_layers: int,
                 activation_epoch: EpochNumber,
                 exit_epoch: EpochNumber,
                 withdrawal_epoch: EpochNumber,
                 penalized_epoch: EpochNumber,
                 exit_count: int,
                 status_flags: int) -> None:
        super().__init__(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            randao_commitment=randao_commitment,
            randao_layers=randao_layers,
            activation_epoch=activation_epoch,
            exit_epoch=exit_epoch,
            withdrawal_epoch=withdrawal_epoch,
            penalized_epoch=penalized_epoch,
            exit_count=exit_count,
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
                                 withdrawal_credentials: Hash32,
                                 randao_commitment: Hash32) -> 'ValidatorRecord':
        """
        Return a new pending ``ValidatorRecord`` with the given fields.
        """
        return cls(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            randao_commitment=randao_commitment,
            randao_layers=0,
            activation_epoch=FAR_FUTURE_EPOCH,
            exit_epoch=FAR_FUTURE_EPOCH,
            withdrawal_epoch=FAR_FUTURE_EPOCH,
            penalized_epoch=FAR_FUTURE_EPOCH,
            exit_count=0,
            status_flags=0,
        )
