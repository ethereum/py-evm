import pytest

from eth.beacon.enums import (
    ValidatorStatusCode,
)
from eth.beacon.types.validator_records import (
    ValidatorRecord,
)


def test_defaults(sample_validator_record_params):
    validator = ValidatorRecord(**sample_validator_record_params)
    assert validator.pubkey == sample_validator_record_params['pubkey']
    assert validator.withdrawal_credentials == sample_validator_record_params['withdrawal_credentials']  # noqa: E501


@pytest.mark.parametrize(
    'status,expected',
    [
        (ValidatorStatusCode.PENDING_ACTIVATION, False),
        (ValidatorStatusCode.ACTIVE, True),
        (ValidatorStatusCode.ACTIVE_PENDING_EXIT, True),
        (ValidatorStatusCode.EXITED_WITHOUT_PENALTY, False),
        (ValidatorStatusCode.EXITED_WITH_PENALTY, False),
    ],
)
def test_is_active(sample_validator_record_params,
                   status,
                   expected):
    validator_record_params = {
        **sample_validator_record_params,
        'status': status
    }
    validator = ValidatorRecord(**validator_record_params)
    assert validator.is_active == expected
