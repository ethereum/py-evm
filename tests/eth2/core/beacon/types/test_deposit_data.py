from eth2.beacon.types.deposit_data import DepositData


def test_defaults(sample_deposit_data_params):
    deposit_data = DepositData(**sample_deposit_data_params)

    assert deposit_data.deposit_input.pubkey == sample_deposit_data_params['deposit_input'].pubkey
    assert deposit_data.amount == sample_deposit_data_params['amount']
    assert deposit_data.timestamp == sample_deposit_data_params['timestamp']
