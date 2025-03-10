"""
Implementation heavily inspired by ``ethereum/execution-specs`` implementation for the
prague network upgrade. This implementation keeps points in optimized (x, y, z)
coordinates.
"""

from typing import (
    Optional,
    Tuple,
)

from py_ecc.bls.hash_to_curve import (
    clear_cofactor_G1,
    map_to_curve_G1,
)
from py_ecc.fields import (
    optimized_bls12_381_FQ as OPTIMIZED_FQ,
)
from py_ecc.optimized_bls12_381.optimized_curve import (
    add as bls12_add_optimized,
    b,
    curve_order,
    is_inf,
    is_on_curve,
    multiply as bls12_multiply_optimized,
    normalize,
)
from py_ecc.typing import (
    Optimized_Point3D,
)

from eth.abc import (
    ComputationAPI,
)
from eth.exceptions import (
    VMError,
)

from .constants import (
    BLS12_G1_ADD_GAS,
    BLS12_G1_MSM_GAS,
    BLS12_MAP_FP_G1_GAS,
    G1_MSM_DISCOUNTS,
    G1_MSM_MAX_DISCOUNT,
    MSM_MULTIPLIER,
)

MSM_LEN_PER_PAIR = 160

# -- utils -- #


def bytes_to_g1_optimized_point3D(
    data: bytes,
) -> Optional[Optimized_Point3D[OPTIMIZED_FQ]]:
    if not len(data) == 128:
        raise VMError("Length of data must be 128 bytes for G1 point")

    x, y = (
        int.from_bytes(data[:64], "big"),
        int.from_bytes(data[64:], "big"),
    )

    if x >= OPTIMIZED_FQ.field_modulus:
        raise VMError("x >= field modulus")
    if y >= OPTIMIZED_FQ.field_modulus:
        raise VMError("y >= field modulus")

    z = 0 if (x == 0 and y == 0) else 1
    point = OPTIMIZED_FQ(x), OPTIMIZED_FQ(y), OPTIMIZED_FQ(z)

    if not is_on_curve(point, b):
        raise VMError("Point is not on curve")

    return point


def g1_optimized_3d_to_bytes(
    g1_optimized_3d: Optimized_Point3D[OPTIMIZED_FQ],
) -> bytes:
    g1_normalized = normalize(g1_optimized_3d)
    x, y = g1_normalized
    return b"".join([int(x).to_bytes(64, "big"), int(y).to_bytes(64, "big")])


def decode_g1_scalar_pair(data: bytes) -> Tuple[Optimized_Point3D[OPTIMIZED_FQ], int]:
    if len(data) != 160:
        raise VMError("Length of data must be 160 bytes for G1 scalar pair")

    point = bytes_to_g1_optimized_point3D(data[:128])

    if not is_inf(bls12_multiply_optimized(point, curve_order)):
        raise VMError("Point failed sub-group check.")

    n = int.from_bytes(data[128 : 128 + 32], "big")

    return point, n


# -- functions -- #


def bls12_g1_add(computation: ComputationAPI) -> None:
    data = computation.msg.data

    if len(data) != 256:
        raise VMError("Length of data must be 256 bytes for BLS12_G1ADD")

    computation.consume_gas(BLS12_G1_ADD_GAS, reason="BLS12_G1ADD gas")

    p1 = bytes_to_g1_optimized_point3D(data[:128])
    p2 = bytes_to_g1_optimized_point3D(data[128:])

    result = bls12_add_optimized(p1, p2)

    computation.output = g1_optimized_3d_to_bytes(result)


def bls12_g1_msm(computation: ComputationAPI) -> None:
    data = computation.msg.data

    if len(data) == 0 or len(data) % MSM_LEN_PER_PAIR != 0:
        raise VMError("Length of data must be a multiple of 128 bytes for BLS12_G1MSM")

    k = len(data) // MSM_LEN_PER_PAIR
    discount = G1_MSM_DISCOUNTS[k - 1] if k <= 128 else G1_MSM_MAX_DISCOUNT

    gas_cost = k * BLS12_G1_MSM_GAS * discount // MSM_MULTIPLIER
    computation.consume_gas(gas_cost, reason="BLS12_G1MSM gas")

    result = None
    for i in range(k):
        start_index = i * MSM_LEN_PER_PAIR
        end_index = start_index + MSM_LEN_PER_PAIR

        point, n = decode_g1_scalar_pair(data[start_index:end_index])
        product = bls12_multiply_optimized(point, n)

        if i == 0:
            result = product
        else:
            result = bls12_add_optimized(result, product)

    computation.output = g1_optimized_3d_to_bytes(result)


def bls12_map_fp_to_g1(computation: ComputationAPI) -> None:
    data = computation.msg.data

    if len(data) != 64:
        raise VMError("Length of data must be 64 bytes for BLS12_MAP_FP_TO_G1")

    computation.consume_gas(BLS12_MAP_FP_G1_GAS, reason="BLS12_MAP_FP_TO_G1 gas")

    fp = int.from_bytes(data, "big")
    if fp >= OPTIMIZED_FQ.field_modulus:
        raise VMError("coordinate >= field modulus")

    g1_optimized_3d = clear_cofactor_G1(map_to_curve_G1(OPTIMIZED_FQ(fp)))

    computation.output = g1_optimized_3d_to_bytes(g1_optimized_3d)
