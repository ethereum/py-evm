from eth_typing import (
    BLSPubkey,
    BLSSignature,
    Hash32,
)
import ssz
from ssz.sedes import (
    bytes32,
    bytes48,
    bytes96,
)

from eth2.beacon.constants import EMPTY_SIGNATURE


class DepositInput(ssz.SignedSerializable):

    fields = [
        # BLS pubkey
        ('pubkey', bytes48),
        # Withdrawal credentials
        ('withdrawal_credentials', bytes32),
        # BLS proof of possession (a BLS signature)
        ('signature', bytes96),
    ]

    def __init__(self,
                 pubkey: BLSPubkey,
                 withdrawal_credentials: Hash32,
                 signature: BLSSignature=EMPTY_SIGNATURE) -> None:
        super().__init__(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            signature=signature,
        )
