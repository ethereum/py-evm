from eth.beacon.types.deposit_parameters import DepositParameters


def test_defaults(sample_deposit_parameters_params):
    deposit_parameters = DepositParameters(**sample_deposit_parameters_params)

    assert deposit_parameters.pubkey == sample_deposit_parameters_params['pubkey']
