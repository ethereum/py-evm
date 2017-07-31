import pytest

from evm.vm.gas_meter import (
    GasMeter,
)
from evm.exceptions import (
    ValidationError,
    OutOfGas,
)


@pytest.fixture
def gas_meter():
    return GasMeter(10)


@pytest.mark.parametrize(
    "value,is_valid",
    (
        (-1, False),
        (0, True),
        (10, True),
        (2**256, False),
        ('a', False),
    )
)
def test_start_gas_on_instantiation(value, is_valid):
    if is_valid:
        meter = GasMeter(value)
        assert meter.start_gas == value
        assert meter.gas_remaining == value
        assert meter.gas_refunded == 0
    else:
        with pytest.raises(ValidationError):
            GasMeter(value)


@pytest.mark.parametrize(
    "consume,reason,is_valid",
    (
        (-1, "Reason", False),
        (0, "Reason", True),
        (1, "Reason", True),
    )
)
def test_consume_gas_rejects_negative_values(gas_meter, consume, reason, is_valid):
    if is_valid:
        gas_meter.consume_gas(consume, reason)
        assert gas_meter.gas_remaining == gas_meter.start_gas - consume
    else:
        with pytest.raises(ValidationError):
            gas_meter.consume_gas(consume, reason)


@pytest.mark.parametrize(
    "return_amt,is_valid",
    (
        (-1, False),
        (0, True),
        (1, True),
    )
)
def test_return_gas_rejects_negative_values(gas_meter, return_amt, is_valid):
    if is_valid:
        gas_meter.return_gas(return_amt)
        assert gas_meter.gas_remaining == (gas_meter.start_gas + return_amt)
    else:
        with pytest.raises(ValidationError):
            gas_meter.return_gas(return_amt)


@pytest.mark.parametrize(
    "refund,is_valid",
    (
        (-1, False),
        (0, True),
        (1, True),
    )
)
def test_refund_gas_rejects_negative_values(gas_meter, refund, is_valid):
    if is_valid:
        gas_meter.refund_gas(refund)
        assert gas_meter.gas_refunded == refund
    else:
        with pytest.raises(ValidationError):
            gas_meter.refund_gas(refund)


@pytest.mark.parametrize(
    "consume,reason,is_valid",
    (
        (10, "Reason", True),
        (11, "Reason", False),
    )
)
def test_consume_gas_spends_or_raises_exception(gas_meter, consume, reason, is_valid):
    assert gas_meter.gas_remaining == 10
    if is_valid:
        gas_meter.consume_gas(consume, reason)
        assert gas_meter.gas_remaining == 0
    else:
        with pytest.raises(OutOfGas):
            gas_meter.consume_gas(consume, reason)


def test_consumption_return_refund_work_correctly(gas_meter):
    assert gas_meter.gas_remaining == 10
    assert gas_meter.gas_refunded == 0
    gas_meter.consume_gas(5, "Reason")
    assert gas_meter.gas_remaining == 5
    gas_meter.return_gas(5)
    assert gas_meter.gas_remaining == 10
    gas_meter.refund_gas(5)
    assert gas_meter.gas_refunded == 5
