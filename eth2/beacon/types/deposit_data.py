from eth.constants import (
    ZERO_HASH32,
)
from eth_typing import (
    BLSPubkey,
    BLSSignature,
    Hash32,
)
from eth_utils import (
    encode_hex,
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

from .defaults import (
    default_bls_pubkey,
    default_gwei,
)


class DepositData(ssz.SignedSerializable):
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
                 pubkey: BLSPubkey=default_bls_pubkey,
                 withdrawal_credentials: Hash32=ZERO_HASH32,
                 amount: Gwei=default_gwei,
                 signature: BLSSignature=EMPTY_SIGNATURE) -> None:
        super().__init__(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            amount=amount,
            signature=signature,
        )

    def __repr__(self) -> str:
        return f"<DepositData root: {encode_hex(self.root)[0:8]}>"


default_deposit_data = DepositData()
