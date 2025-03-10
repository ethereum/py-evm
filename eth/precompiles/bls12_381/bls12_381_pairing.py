"""
Implementation heavily inspired by ``ethereum/execution-specs`` implementation for the
prague network upgrade. This implementation keeps points in optimized (x, y, z)
coordinates.
"""

from py_ecc.optimized_bls12_381 import (
    pairing,
)
from py_ecc.optimized_bls12_381.optimized_curve import (
    FQ12,
    curve_order,
    is_inf,
    multiply as bls12_multiply_optimized,
)

from eth.abc import (
    ComputationAPI,
)
from eth.exceptions import (
    VMError,
)
from eth.precompiles.bls12_381.bls12_381_g1 import (
    bytes_to_g1_optimized_point3D,
)
from eth.precompiles.bls12_381.bls12_381_g2 import (
    bytes_to_g2_optimized_point3D,
)


def bls12_pairing_check(computation: ComputationAPI) -> None:
    data = computation.msg.data
    if len(data) == 0 or len(data) % 384 != 0:
        raise VMError(
            "Length of data must be a multiple of 384 bytes for BLS12_PAIRING_CHECK"
        )

    k = len(data) // 384
    gas_cost = 32600 * k + 37700
    computation.consume_gas(gas_cost, "BLS12_PAIRING_CHECK gas")

    result = FQ12.one()
    for i in range(k):
        g1_start = 384 * i
        g2_start = 384 * i + 128

        g1_point = bytes_to_g1_optimized_point3D(data[g1_start : g1_start + 128])
        if not is_inf(bls12_multiply_optimized(g1_point, curve_order)):
            raise VMError("Sub-group check failed for G1 point.")

        g2_point = bytes_to_g2_optimized_point3D(data[g2_start : g2_start + 256])
        if not is_inf(bls12_multiply_optimized(g2_point, curve_order)):
            raise VMError("Sub-group check failed for G2 point.")

        result *= pairing(g2_point, g1_point)

    computation.output = (
        b"\x00" * 31 + b"\x01" if result == FQ12.one() else b"\x00" * 32
    )
