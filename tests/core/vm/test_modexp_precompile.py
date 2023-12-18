import json
import os

from eth_utils import (
    decode_hex,
)
import pytest

from eth.precompiles.modexp import (
    _compute_modexp_gas_fee_eip_198,
    _modexp,
)
from eth.vm.forks.berlin.computation import (
    _compute_modexp_gas_fee_eip_2565,
)


def vectors():
    filepath = os.path.join(
        os.path.dirname(__file__), "fixtures/modexp_precompile_test_vectors.json"
    )
    f = open(filepath)
    return json.load(f)


def eip_198_gas_cost_vectors():
    return [(decode_hex(v["input"]), v["eip_198_gas"]) for v in vectors()]


def eip_2565_gas_cost_vectors():
    return [(decode_hex(v["input"]), v["eip_2565_gas"]) for v in vectors()]


def modexp_result():
    return [(decode_hex(v["input"]), int(v["expected"], 16)) for v in vectors()]


@pytest.mark.parametrize("data,expected", eip_198_gas_cost_vectors())
def test_modexp_gas_fee_calculation(data, expected):
    actual = _compute_modexp_gas_fee_eip_198(data)
    assert actual == expected


@pytest.mark.parametrize("data,expected", eip_2565_gas_cost_vectors())
def test_modexp_gas_fee_calculation_eip_2565(data, expected):
    actual = _compute_modexp_gas_fee_eip_2565(data)
    assert actual == expected


@pytest.mark.parametrize("data,expected", modexp_result())
def test_modexp_result(data, expected):
    actual = _modexp(data)
    assert actual == expected
