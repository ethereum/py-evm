import pytest

from eth2.beacon.constants import FAR_FUTURE_EPOCH, GWEI_PER_ETH
from eth2.beacon.types.validators import Validator
from eth2.beacon.typing import Gwei


def test_defaults(sample_validator_record_params):
    validator = Validator(**sample_validator_record_params)
    assert validator.pubkey == sample_validator_record_params["pubkey"]
    assert (
        validator.withdrawal_credentials
        == sample_validator_record_params["withdrawal_credentials"]
    )  # noqa: E501


@pytest.mark.parametrize(
    "activation_epoch,exit_epoch,epoch,expected",
    [(0, 1, 0, True), (1, 1, 1, False), (0, 1, 1, False), (0, 1, 2, False)],
)
def test_is_active(
    sample_validator_record_params, activation_epoch, exit_epoch, epoch, expected
):
    validator_record_params = {
        **sample_validator_record_params,
        "activation_epoch": activation_epoch,
        "exit_epoch": exit_epoch,
    }
    validator = Validator(**validator_record_params)
    assert validator.is_active(epoch) == expected


def test_create_pending_validator(config):
    pubkey = 123
    withdrawal_credentials = b"\x11" * 32

    effective_balance = 22 * GWEI_PER_ETH
    amount = Gwei(effective_balance + config.EFFECTIVE_BALANCE_INCREMENT // 2)
    validator = Validator.create_pending_validator(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        amount=amount,
        config=config,
    )

    assert validator.pubkey == pubkey
    assert validator.withdrawal_credentials == withdrawal_credentials
    assert validator.activation_epoch == FAR_FUTURE_EPOCH
    assert validator.exit_epoch == FAR_FUTURE_EPOCH
    assert validator.slashed is False
    assert validator.effective_balance == effective_balance
