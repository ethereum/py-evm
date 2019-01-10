import pytest

from eth2.beacon.constants import (
    FAR_FUTURE_SLOT,
)
from eth2.beacon.types.validator_records import (
    ValidatorRecord,
)


def test_defaults(sample_validator_record_params):
    validator = ValidatorRecord(**sample_validator_record_params)
    assert validator.pubkey == sample_validator_record_params['pubkey']
    assert validator.withdrawal_credentials == sample_validator_record_params['withdrawal_credentials']  # noqa: E501


@pytest.mark.parametrize(
    'activation_slot,exit_slot,slot,expected',
    [
        (0, 1, 0, True),
        (1, 1, 1, False),
        (0, 1, 1, False),
        (0, 1, 2, False),
    ],
)
def test_is_active(sample_validator_record_params,
                   activation_slot,
                   exit_slot,
                   slot,
                   expected):
    validator_record_params = {
        **sample_validator_record_params,
        'activation_slot': activation_slot,
        'exit_slot': exit_slot,
    }
    validator = ValidatorRecord(**validator_record_params)
    assert validator.is_active(slot) == expected


def test_create_pending_validator():
    pubkey = 123
    withdrawal_credentials = b'\x11' * 32
    randao_commitment = b'\x22' * 32
    custody_commitment = b'\x33' * 32

    validator = ValidatorRecord.create_pending_validator(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        randao_commitment=randao_commitment,
        custody_commitment=custody_commitment,
    )

    assert validator.pubkey == pubkey
    assert validator.withdrawal_credentials == withdrawal_credentials
    assert validator.randao_commitment == randao_commitment
    assert validator.randao_layers == 0
    assert validator.activation_slot == FAR_FUTURE_SLOT
    assert validator.exit_slot == FAR_FUTURE_SLOT
    assert validator.withdrawal_slot == FAR_FUTURE_SLOT
    assert validator.penalized_slot == FAR_FUTURE_SLOT
    assert validator.exit_count == 0
