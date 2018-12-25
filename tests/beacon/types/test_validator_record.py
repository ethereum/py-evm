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


def test_get_pending_validator():
    pubkey = 123
    withdrawal_credentials = b'\x11' * 32
    randao_commitment = b'\x22' * 32
    latest_status_change_slot = 10
    custody_commitment = b'\x33' * 32

    validator = ValidatorRecord.get_pending_validator(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        randao_commitment=randao_commitment,
        latest_status_change_slot=latest_status_change_slot,
        custody_commitment=custody_commitment,
    )

    assert validator.pubkey == pubkey
    assert validator.withdrawal_credentials == withdrawal_credentials
    assert validator.randao_commitment == randao_commitment
    assert validator.latest_status_change_slot == latest_status_change_slot

    assert validator.status == ValidatorStatusCode.PENDING_ACTIVATION
    assert validator.randao_layers == 0
    assert validator.exit_count == 0
