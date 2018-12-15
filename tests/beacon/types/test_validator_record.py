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


def test_is_active(sample_validator_record_params):
    validator_record_params = {
        **sample_validator_record_params,
        'status': ValidatorStatusCode.ACTIVE
    }
    validator = ValidatorRecord(**validator_record_params)
    assert validator.is_active

    validator_record_params = {
        **sample_validator_record_params,
        'status': ValidatorStatusCode.ACTIVE_PENDING_EXIT
    }
    validator = ValidatorRecord(**validator_record_params)
    assert validator.is_active

    validator_record_params = {
        **sample_validator_record_params,
        'status': ValidatorStatusCode.EXITED_WITHOUT_PENALTY
    }
    validator = ValidatorRecord(**validator_record_params)
    assert not validator.is_active
