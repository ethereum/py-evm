import pytest

from eth.beacon.types.validator_records import (
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


def test_get_pending_validator():
    pubkey = 123
    withdrawal_credentials = b'\x11' * 32
    randao_commitment = b'\x22' * 32
    custody_commitment = b'\x33' * 32
    far_future_slot = 1000

    validator = ValidatorRecord.get_pending_validator(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        randao_commitment=randao_commitment,
        custody_commitment=custody_commitment,
        far_future_slot=far_future_slot,
    )

    assert validator.pubkey == pubkey
    assert validator.withdrawal_credentials == withdrawal_credentials
    assert validator.randao_commitment == randao_commitment
    assert validator.randao_layers == 0
    assert validator.activation_slot == far_future_slot
    assert validator.exit_slot == far_future_slot
    assert validator.withdrawal_slot == far_future_slot
    assert validator.penalized_slot == far_future_slot
    assert validator.exit_count == 0
