import pytest

from evm.precompiles.modexp import (
    _modexp,
    _compute_modexp_gas_fee,
)
from evm.utils.hexadecimal import (
    decode_hex,
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
            708647586132375115992254428253169996062012306153720251921480414128428353393856280,
        ),
    ),
)
def test_modexp_gas_fee_calcultation(data, expected):
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
