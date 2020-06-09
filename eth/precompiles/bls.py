from typing import Tuple

from eth_utils import (
    ValidationError,
    big_endian_to_int,
)
from py_ecc import (
    optimized_bls12_381 as bls12_381,
    bls
)

from eth import constants
from eth.exceptions import (
    VMError,
)

from eth.vm.computation import (
    BaseComputation,
)


FP2_SIZE_IN_BYTES = 128
G1_SIZE_IN_BYTES = 128
G2_SIZE_IN_BYTES = 256

G1Point = Tuple[bls12_381.FQ, bls12_381.FQ]
G2Point = Tuple[bls12_381.FQ2, bls12_381.FQ2]


def _parse_g1_point(data: bytes) -> G1Point:
    if len(data) != G1_SIZE_IN_BYTES:
        raise ValidationError("invalid size of G1 input")

    x = bls12_381.FQ(int.from_bytes(data[0:64], byteorder="big"))
    y = bls12_381.FQ(int.from_bytes(data[64:128], byteorder="big"))
    point = (x, y)

    if not bls12_381.is_on_curve((x, y, bls12_381.FQ.one()), bls12_381.b):
        raise ValidationError("invalid G1 point not on curve")

    return point


def g1_add(computation: BaseComputation,
           gas_cost: int = constants.GAS_BLS_G1_ADD) -> BaseComputation:
    raise NotImplementedError()


def g1_mul(computation: BaseComputation,
           gas_cost: int = constants.GAS_BLS_G1_MUL) -> BaseComputation:
    raise NotImplementedError()


def g1_multiexp(computation: BaseComputation) -> BaseComputation:
    # NOTE: gas cost involves a discount based on the number of points involved
    # TODO load discount table and compute gas cost based on number of inputs
    raise NotImplementedError()


def _parse_g2_point(data: bytes) -> G2Point:
    if len(data) != G2_SIZE_IN_BYTES:
        raise ValidationError("invalid size of G2 input")

    x = bls12_381.FQ2(
        (
            int.from_bytes(data[0:64], byteorder="big"),
            int.from_bytes(data[64:128], byteorder="big")
        )
    )
    y = bls12_381.FQ2(
        (
            int.from_bytes(data[128:192], byteorder="big"),
            int.from_bytes(data[192:256], byteorder="big")
        )
    )
    point = (x, y)

    if not bls12_381.is_on_curve((x, y, bls12_381.FQ2.one()), bls12_381.b2):
        raise ValidationError("invalid G2 point not on curve")

    return point


def _serialize_g2(result: G2Point) -> bytes:
    return b"".join(
        (
            result[0].coeffs[0].to_bytes(64, byteorder="big"),
            result[0].coeffs[1].to_bytes(64, byteorder="big"),
            result[1].coeffs[0].to_bytes(64, byteorder="big"),
            result[1].coeffs[1].to_bytes(64, byteorder="big"),
        )
    )


def _g2_add(x: G2Point, y: G2Point) -> G2Point:
    result = bls12_381.add((x[0], x[1], bls12_381.FQ2.one()), (y[0], y[1], bls12_381.FQ2.one()))
    return bls12_381.normalize(result)


def g2_add(computation: BaseComputation,
           gas_cost: int = constants.GAS_BLS_G2_ADD) -> BaseComputation:
    computation.consume_gas(gas_cost, reason='BLS_G2_ADD Precompile')

    try:
        input_data = computation.msg.data_as_bytes
        x = _parse_g2_point(input_data[:G2_SIZE_IN_BYTES])
        y = _parse_g2_point(input_data[G2_SIZE_IN_BYTES:])
        result = _g2_add(x, y)
    except ValidationError:
        raise VMError("Invalid BLS_G2_ADD parameters")

    computation.output = _serialize_g2(result)
    return computation


def _g2_mul(x: G2Point, k: int) -> G2Point:
    result = bls12_381.multiply((x[0], x[1], bls12_381.FQ2.one()), k)
    return bls12_381.normalize(result)


def _parse_scalar(data: bytes) -> int:
    if len(data) != 32:
        raise ValidationError("invalid size of scalar input")

    return big_endian_to_int(data)


def g2_mul(computation: BaseComputation,
           gas_cost: int = constants.GAS_BLS_G2_MUL) -> BaseComputation:
    computation.consume_gas(gas_cost, reason='BLS_G2_MUL Precompile')

    try:
        input_data = computation.msg.data_as_bytes
        x = _parse_g2_point(input_data[:G2_SIZE_IN_BYTES])
        k = _parse_scalar(input_data[G2_SIZE_IN_BYTES:])
        result = _g2_mul(x, k)
    except ValidationError:
        raise VMError("Invalid BLS_G2_MUL parameters")

    computation.output = _serialize_g2(result)
    return computation


def g2_multiexp(computation: BaseComputation) -> BaseComputation:
    # NOTE: gas cost involves a discount based on the number of points involved
    # TODO load discount table and compute gas cost based on number of inputs
    raise NotImplementedError()


def _pairing(input_data: bytes) -> bool:
    field_element = bls12_381.FQ12.one()
    g1_to_g2_offset = G1_SIZE_IN_BYTES + G2_SIZE_IN_BYTES
    for next_index in range(0, len(input_data), 384):
        p = _parse_g1_point(input_data[next_index:next_index + G1_SIZE_IN_BYTES])

        q = _parse_g2_point(
            input_data[next_index + G1_SIZE_IN_BYTES:next_index + g1_to_g2_offset]
        )
        projective_p = (p[0], p[1], bls12_381.FQ.one())
        projective_q = (q[0], q[1], bls12_381.FQ2.one())
        field_element *= bls12_381.pairing(projective_q, projective_p, final_exponentiate=False)

    return bls12_381.final_exponentiate(field_element) == bls12_381.FQ12.one()


def _serialize_boolean(value: bool) -> bytes:
    return int(value).to_bytes(32, byteorder="big")


def pairing(computation: BaseComputation,
            gas_cost_base: int = constants.GAS_BLS_PAIRING_BASE,
            gas_cost_per_pair: int = constants.GAS_BLS_PAIRING_PER_PAIR) -> BaseComputation:
    input_data = computation.msg.data_as_bytes
    if len(input_data) % 384:
        # data length must be an exact multiple of 384
        raise VMError("Invalid BLS_PAIRING parameters")

    num_points = len(input_data) // 384
    gas_cost = gas_cost_base + num_points * gas_cost_per_pair

    computation.consume_gas(gas_cost, reason='BLS_PAIRING Precompile')

    try:
        result = _pairing(input_data)
    except ValidationError:
        raise VMError("Invalid BLS_PAIRING parameters")

    computation.output = _serialize_boolean(result)
    return computation


def map_fp_to_g1(computation: BaseComputation,
                 gas_cost: int = constants.GAS_BLS_MAP_FP_TO_G1) -> BaseComputation:
    raise NotImplementedError()


def _parse_fp2_element(data: bytes) -> bls12_381.FQ2:
    if len(data) != FP2_SIZE_IN_BYTES:
        raise ValidationError("invalid size of FP2 input")

    return bls12_381.FQ2(
        (
            int.from_bytes(data[:64], byteorder="big"),
            int.from_bytes(data[64:], byteorder="big")
        )
    )


def _map_fp2_to_g2(field_element: bls12_381.FQ2) -> G2Point:
    point = bls.hash_to_curve.map_to_curve_G2(field_element)
    group_element = bls.hash_to_curve.clear_cofactor_G2(point)
    return bls12_381.normalize(group_element)


def map_fp2_to_g2(computation: BaseComputation,
                  gas_cost: int = constants.GAS_BLS_MAP_FP2_TO_G2) -> BaseComputation:
    computation.consume_gas(gas_cost, reason='BLS_MAP_FP2_TO_G2 Precompile')

    try:
        input_data = computation.msg.data_as_bytes
        field_element = _parse_fp2_element(input_data[:FP2_SIZE_IN_BYTES])
        result = _map_fp2_to_g2(field_element)
    except ValidationError:
        raise VMError("Invalid BLS_MAP_FP2_TO_G2 parameters")

    computation.output = _serialize_g2(result)
    return computation
