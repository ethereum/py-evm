from eth_typing import (
    BLSPubkey,
    BLSSignature,
)
import ssz
from ssz.sedes import (
    bytes48,
    bytes96,
    uint64
)

from eth2.beacon.constants import EMPTY_SIGNATURE

from eth2.beacon.typing import (
    Gwei,
    Slot,
    ValidatorIndex,
)

from .defaults import (
    default_validator_index,
    default_gwei,
    default_slot,
    default_bls_pubkey,
)


class Transfer(ssz.SignedSerializable):
    fields = [
        ('sender', uint64),
        ('recipient', uint64),
        ('amount', uint64),
        ('fee', uint64),
        # Inclusion slot
        ('slot', uint64),
        # Sender withdrawal pubkey
        ('pubkey', bytes48),
        # Sender signature
        ('signature', bytes96),
    ]

    def __init__(self,
                 sender: ValidatorIndex=default_validator_index,
                 recipient: ValidatorIndex=default_validator_index,
                 amount: Gwei=default_gwei,
                 fee: Gwei=default_gwei,
                 slot: Slot=default_slot,
                 pubkey: BLSPubkey=default_bls_pubkey,
                 signature: BLSSignature=EMPTY_SIGNATURE) -> None:
        super().__init__(
            sender=sender,
            recipient=recipient,
            amount=amount,
            fee=fee,
            slot=slot,
            pubkey=pubkey,
            signature=signature,
        )
