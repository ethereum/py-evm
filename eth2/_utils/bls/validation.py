from py_ecc.optimized_bls12_381 import (
    curve_order,
)
from eth_typing import (
    BLSSignature,
)
from eth_utils import (
    ValidationError,
)


def validate_private_key(privkey: int) -> None:
    if privkey <= 0 or privkey >= curve_order:
        raise ValidationError(
            f"Invalid private key: Expect integer between 1 and {curve_order - 1}, got {privkey}"
        )


def validate_signature(signature: BLSSignature) -> None:
    if len(signature) != 96:
        raise ValidationError(
            f"Invalid signaute length, expect 96 got {len(signature)}. Signature: {signature}"
        )
