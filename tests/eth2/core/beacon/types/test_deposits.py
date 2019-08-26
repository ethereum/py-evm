from eth2.beacon.types.deposits import Deposit


def test_defaults(sample_deposit_params):
    deposit = Deposit(**sample_deposit_params)

    assert deposit.data == sample_deposit_params["data"]
