from eth.beacon.types.validator_records import (
    ValidatorRecord,
)


def test_defaults(sample_validator_record_params):
    validator = ValidatorRecord(**sample_validator_record_params)
    assert validator.pubkey == sample_validator_record_params['pubkey']
    assert validator.withdrawal_credentials == \
        sample_validator_record_params['withdrawal_credentials']
