import pytest

from eth.constants import (
    ZERO_ADDRESS,
    ZERO_HASH32,
)
from eth.beacon.types.validator_record import (
    ValidatorRecord,
)


@pytest.mark.parametrize(
    'param,default_value',
    [
        ('pubkey', b''),
        ('withdrawal_shard', 0),
        ('withdrawal_address', ZERO_ADDRESS),
        ('randao_commitment', ZERO_HASH32),
        ('balance', 0),
        ('start_dynasty', 0),
        ('end_dynasty', 0),
    ]
)
def test_defaults(param, default_value, sample_validator_record_params):
    del sample_validator_record_params[param]
    validator_record = ValidatorRecord(**sample_validator_record_params)

    assert getattr(validator_record, param) == default_value
