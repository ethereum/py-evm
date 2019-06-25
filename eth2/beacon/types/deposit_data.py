from eth.constants import (
    ZERO_HASH32,
)
from eth_typing import (
    BLSPubkey,
    BLSSignature,
    Hash32,
)
import ssz
from ssz.sedes import (
    uint64,
    bytes32,
    bytes48,
    bytes96,
)

from eth2.beacon.constants import EMPTY_SIGNATURE
from eth2.beacon.typing import (
    Gwei,
)


class DepositData(ssz.Serializable):
    """
    :class:`~eth2.beacon.types.deposit_data.DepositData` corresponds to the data broadcast from the
    Ethereum 1.0 deposit contract after a successful call to the ``deposit`` function on that
    contract.
    """
    fields = [
        ('pubkey', bytes48),
        ('withdrawal_credentials', bytes32),
        ('amount', uint64),
        # BLS proof of possession (a BLS signature)
        ('signature', bytes96),
    ]

    def __init__(self,
                 pubkey: BLSPubkey=b'\x00' * 48,
                 withdrawal_credentials: Hash32=ZERO_HASH32,
                 amount: Gwei=0,
                 signature: BLSSignature=EMPTY_SIGNATURE) -> None:
        super().__init__(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            amount=amount,
            signature=signature,
        )
