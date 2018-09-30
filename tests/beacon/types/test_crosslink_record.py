import pytest

from eth.beacon.types.crosslink_record import (
    CrosslinkRecord,
)
from eth.constants import (
    ZERO_HASH32,
)


@pytest.mark.parametrize(
    'param,default_value',
    [
        ('dynasty', 0),
        ('slot', 0),
        ('hash', ZERO_HASH32),
    ]
)
def test_defaults(param, default_value, sample_crosslink_record_params):
    del sample_crosslink_record_params[param]
    crosslink = CrosslinkRecord(**sample_crosslink_record_params)

    assert getattr(crosslink, param) == default_value
