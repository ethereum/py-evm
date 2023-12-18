from eth_utils import (
    ValidationError,
)
import pytest

from eth.exceptions import (
    OutOfGas,
)
from eth.vm.gas_meter import (
    GasMeter,
)


@pytest.fixture(params=[10, 100, 999])
def gas_meter(request):
    return GasMeter(request.param)


@pytest.mark.parametrize("value", (0, 10))
def test_start_gas_on_instantiation(value):
    meter = GasMeter(value)
    assert meter.start_gas == value
    assert meter.gas_remaining == value
    assert meter.gas_refunded == 0


@pytest.mark.parametrize("value", (-1, 2**256, "a"))
def test_instantiation_invalid_value(value):
    with pytest.raises(ValidationError):
        GasMeter(value)


@pytest.mark.parametrize("amount", (0, 1, 10))
def test_consume_gas(gas_meter, amount):
    gas_meter.consume_gas(amount, "reason")
    assert gas_meter.gas_remaining == gas_meter.start_gas - amount


def test_consume_gas_rejects_negative_values(gas_meter):
    with pytest.raises(ValidationError):
        gas_meter.consume_gas(-1, "reason")


@pytest.mark.parametrize("amount", (0, 1, 99))
def test_return_gas(gas_meter, amount):
    gas_meter.return_gas(amount)
    assert gas_meter.gas_remaining == (gas_meter.start_gas + amount)


def test_return_gas_rejects_negative_values(gas_meter):
    with pytest.raises(ValidationError):
        gas_meter.return_gas(-1)


@pytest.mark.parametrize("amount", (0, 1, 99))
def test_refund_gas(gas_meter, amount):
    gas_meter.refund_gas(amount)
    assert gas_meter.gas_refunded == amount


def test_refund_gas_rejects_negative_values(gas_meter):
    with pytest.raises(ValidationError):
        gas_meter.refund_gas(-1)


def test_consume_gas_spends(gas_meter):
    assert gas_meter.gas_remaining == gas_meter.start_gas
    consume = gas_meter.start_gas
    gas_meter.consume_gas(consume, "reason")
    assert gas_meter.gas_remaining == gas_meter.start_gas - consume


def test_consume_raises_exception(gas_meter):
    assert gas_meter.gas_remaining == gas_meter.start_gas
    with pytest.raises(OutOfGas):
        gas_meter.consume_gas(gas_meter.start_gas + 1, "reason")


def test_consumption_return_refund_work_correctly(gas_meter):
    assert gas_meter.gas_remaining == gas_meter.start_gas
    assert gas_meter.gas_refunded == 0
    gas_meter.consume_gas(5, "Reason")
    assert gas_meter.gas_remaining == gas_meter.start_gas - 5
    gas_meter.return_gas(5)
    assert gas_meter.gas_remaining == gas_meter.start_gas
    gas_meter.refund_gas(5)
    assert gas_meter.gas_refunded == 5
