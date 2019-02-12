import pytest

from eth2.beacon.constants import (
    FAR_FUTURE_EPOCH,
)
from eth2.beacon.types.validator_records import (
    ValidatorRecord,
)


def test_defaults(sample_validator_record_params):
    validator = ValidatorRecord(**sample_validator_record_params)
    assert validator.pubkey == sample_validator_record_params['pubkey']
    assert validator.withdrawal_credentials == sample_validator_record_params['withdrawal_credentials']  # noqa: E501


@pytest.mark.parametrize(
    'activation_epoch,exit_epoch,epoch,expected',
    [
        (0, 1, 0, True),
        (1, 1, 1, False),
        (0, 1, 1, False),
        (0, 1, 2, False),
    ],
)
def test_is_active(sample_validator_record_params,
                   activation_epoch,
                   exit_epoch,
                   epoch,
                   expected):
    validator_record_params = {
        **sample_validator_record_params,
        'activation_epoch': activation_epoch,
        'exit_epoch': exit_epoch,
    }
    validator = ValidatorRecord(**validator_record_params)
    assert validator.is_active(epoch) == expected


def test_create_pending_validator():
    pubkey = 123
    withdrawal_credentials = b'\x11' * 32
    randao_commitment = b'\x22' * 32

    validator = ValidatorRecord.create_pending_validator(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        randao_commitment=randao_commitment,
    )

    assert validator.pubkey == pubkey
    assert validator.withdrawal_credentials == withdrawal_credentials
    assert validator.randao_commitment == randao_commitment
    assert validator.randao_layers == 0
    assert validator.activation_epoch == FAR_FUTURE_EPOCH
    assert validator.exit_epoch == FAR_FUTURE_EPOCH
    assert validator.withdrawal_epoch == FAR_FUTURE_EPOCH
    assert validator.penalized_epoch == FAR_FUTURE_EPOCH
