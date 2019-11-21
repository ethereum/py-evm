from typing import Sequence

from eth_typing import BLSPubkey, BLSSignature
from py_ecc.optimized_bls12_381 import curve_order

from eth2.beacon.constants import EMPTY_PUBKEY, EMPTY_SIGNATURE
from eth2.beacon.exceptions import PublicKeyError, SignatureError


def validate_private_key(privkey: int) -> None:
    if privkey <= 0 or privkey >= curve_order:
        raise ValueError(
            f"Invalid private key: Expect integer between 1 and {curve_order - 1}, got {privkey}"
        )


def validate_public_key(pubkey: BLSPubkey, allow_empty: bool = False) -> None:
    if len(pubkey) != 48:
        raise PublicKeyError(
            f"Invalid public key length, expect 48 got {len(pubkey)}. pubkey: {pubkey.hex()}"
        )
    if not allow_empty and pubkey == EMPTY_PUBKEY:
        raise PublicKeyError(f"Empty public key is invalid  pubkey={pubkey.hex()}")


def validate_many_public_keys(pubkeys: Sequence[BLSPubkey]) -> None:
    for pubkey in pubkeys:
        validate_public_key(pubkey, allow_empty=True)


def validate_signature(signature: BLSSignature) -> None:
    if len(signature) != 96:
        raise SignatureError(
            f"Invalid signaute length, expect 96 got {len(signature)}. Signature: {signature.hex()}"
        )
    if signature == EMPTY_SIGNATURE:
        raise SignatureError(
            f"Signature should not be empty. Signature: {signature.hex()}"
        )
