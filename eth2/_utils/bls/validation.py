from py_ecc.optimized_bls12_381 import (
    curve_order,
)


def validate_private_key(privkey: int) -> None:
    if privkey <= 0 or privkey >= curve_order:
        raise ValueError(
            f"Invalid private key: Expect integer between 1 and {curve_order - 1}, got {privkey}"
        )
