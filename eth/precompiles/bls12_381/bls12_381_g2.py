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
    clear_cofactor_G2,
    map_to_curve_G2,
)
from py_ecc.optimized_bls12_381.optimized_curve import (
    FQ as OPTIMIZED_FQ,
    FQ2 as OPTIMIZED_FQ2,
    add as bls12_add_optimized,
    b2,
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
    BLS12_G2_ADD_GAS,
    BLS12_G2_MSM_GAS,
    BLS12_MAP_FP2_G2_GAS,
    G2_MSM_DISCOUNTS,
    G2_MSM_MAX_DISCOUNT,
    MSM_MULTIPLIER,
)

MSM_LEN_PER_PAIR = 288

# -- utils -- #


def bytes_to_fq2(data: bytes) -> OPTIMIZED_FQ2:
    if len(data) != 128:
        raise VMError("Length of data must be 128 bytes for G2 point")

    coord0 = int.from_bytes(data[:64], "big")
    coord1 = int.from_bytes(data[64:], "big")

    if coord0 >= OPTIMIZED_FQ.field_modulus:
        raise VMError("coordinate 0 >= field modulus")
    if coord1 >= OPTIMIZED_FQ.field_modulus:
        raise VMError("coordinate 1 >= field modulus")

    return OPTIMIZED_FQ2((coord0, coord1))


def fq2_to_bytes(fq2: OPTIMIZED_FQ2) -> bytes:
    coord0, coord1 = fq2.coeffs
    return b"".join(
        [
            int(coord0).to_bytes(64, "big"),
            int(coord1).to_bytes(64, "big"),
        ]
    )


def bytes_to_g2_optimized_point3D(
    data: bytes,
) -> Optional[Optimized_Point3D[OPTIMIZED_FQ2]]:
    if len(data) != 256:
        raise VMError("Length of data must be 256 bytes for G2 point")

    x, y = (bytes_to_fq2(data[:128]), bytes_to_fq2(data[128:]))

    z = (0, 0) if x == OPTIMIZED_FQ2((0, 0)) and y == OPTIMIZED_FQ2((0, 0)) else (1, 0)
    point = x, y, OPTIMIZED_FQ2(z)

    if not is_on_curve(point, b2):
        raise VMError("Point is not on curve")

    return point


def g2_optimized_3d_to_bytes(
    g2_optimized_3d: Optimized_Point3D[OPTIMIZED_FQ2],
) -> bytes:
    g2_normalized = normalize(g2_optimized_3d)
    x_coords, y_coords = g2_normalized
    return b"".join([fq2_to_bytes(x_coords), fq2_to_bytes(y_coords)])


def decode_G2_scalar_pair(data: bytes) -> Tuple[Optimized_Point3D[OPTIMIZED_FQ2], int]:
    if len(data) != 288:
        raise VMError("Length of data must be 288 bytes for G2 scalar pair")

    point = bytes_to_g2_optimized_point3D(data[:256])

    if not is_inf(bls12_multiply_optimized(point, curve_order)):
        raise VMError("Point failed sub-group check.")

    n = int.from_bytes(data[256 : 256 + 32], "big")

    return point, n


# -- functions -- #


def bls12_g2_add(computation: ComputationAPI) -> None:
    data = computation.msg.data

    if len(data) != 512:
        raise VMError("Length of data must be 512 for g2 add")

    computation.consume_gas(BLS12_G2_ADD_GAS, "BLS12_G2ADD gas")

    p1 = bytes_to_g2_optimized_point3D(data[:256])
    p2 = bytes_to_g2_optimized_point3D(data[256 : 256 + 256])

    result = bls12_add_optimized(p1, p2)

    computation.output = g2_optimized_3d_to_bytes(result)


def bls12_g2_msm(computation: ComputationAPI) -> None:
    data = computation.msg.data
    if len(data) == 0 or len(data) % MSM_LEN_PER_PAIR != 0:
        raise VMError(
            "Length of data must be a multiple of 288 bytes for G2 "
            "multi-scalar multiplication"
        )

    k = len(data) // MSM_LEN_PER_PAIR
    discount = G2_MSM_DISCOUNTS[k - 1] if k <= 128 else G2_MSM_MAX_DISCOUNT

    gas_cost = k * BLS12_G2_MSM_GAS * discount // MSM_MULTIPLIER
    computation.consume_gas(gas_cost, "BLS12_G2MSM gas")

    result = None
    for i in range(k):
        start_index = i * MSM_LEN_PER_PAIR
        end_index = start_index + MSM_LEN_PER_PAIR

        p, m = decode_G2_scalar_pair(data[start_index:end_index])
        product = bls12_multiply_optimized(p, m)

        if i == 0:
            result = product
        else:
            result = bls12_add_optimized(result, product)

    computation.output = g2_optimized_3d_to_bytes(result)


def bls12_map_fp2_to_g2(computation: ComputationAPI) -> None:
    data = computation.msg.data
    if len(data) != 128:
        raise VMError("Length of data must be 128 bytes for BLS12_MAP_FP2_TO_G2")

    computation.consume_gas(BLS12_MAP_FP2_G2_GAS, "BLS12_MAP_FP2_TO_G2 gas")

    fp2 = bytes_to_fq2(data)
    g2_optimized_3d = clear_cofactor_G2(map_to_curve_G2(fp2))

    computation.output = g2_optimized_3d_to_bytes(g2_optimized_3d)
