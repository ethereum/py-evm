import pytest

from eth_utils import (
    decode_hex,
)

from eth.precompiles.modexp import (
    _modexp,
    _compute_modexp_gas_fee,
)


EIP198_VECTOR_A = decode_hex(
    "0000000000000000000000000000000000000000000000000000000000000001"
    "0000000000000000000000000000000000000000000000000000000000000020"
    "0000000000000000000000000000000000000000000000000000000000000020"
    "03"
    "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2e"
    "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f"
)

EIP198_VECTOR_B = decode_hex(
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000020"
    "0000000000000000000000000000000000000000000000000000000000000020"
    "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2e"
    "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f"
)

EIP198_VECTOR_C = decode_hex(
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000020"
    "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    "fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffe"
    "fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffd"
)


@pytest.mark.parametrize(
    'data,expected',
    (
        (EIP198_VECTOR_A, 13056),
        (
            EIP198_VECTOR_C,
            10684346944173007063723051170445283632835119638284563472873463025465780712173320789629146724657549280936306536701227228889744512638312451529980055895215896,  # noqa: E501
        ),
    ),
)
def test_modexp_gas_fee_calculation(data, expected):
    actual = _compute_modexp_gas_fee(data)
    assert actual == expected


@pytest.mark.parametrize(
    'data,expected',
    (
        (EIP198_VECTOR_A, 1),
        (EIP198_VECTOR_B, 0),
        (EIP198_VECTOR_C, 0),
    ),
)
def test_modexp_result(data, expected):
    actual = _modexp(data)
    assert actual == expected
