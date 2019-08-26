from eth2.beacon.types.deposit_data import DepositData


def test_defaults(sample_deposit_data_params):
    deposit_data = DepositData(**sample_deposit_data_params)

    assert deposit_data.pubkey == sample_deposit_data_params["pubkey"]
    assert deposit_data.amount == sample_deposit_data_params["amount"]
