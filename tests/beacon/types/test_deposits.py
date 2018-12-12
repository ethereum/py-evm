from eth.beacon.types.deposits import (
    DepositParameters,
    Deposit,
)


def test_deposit_parameters_defaults(sample_deposit_parameters_params):
    deposit_parameters = DepositParameters(**sample_deposit_parameters_params)

    assert deposit_parameters.pubkey == sample_deposit_parameters_params['pubkey']


def test_deposit_defaults(sample_deposit_params):
    deposit = Deposit(**sample_deposit_params)

    assert deposit.deposit_data.timestamp == sample_deposit_params['deposit_data'].timestamp
