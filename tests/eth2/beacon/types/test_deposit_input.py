from eth2.beacon.types.deposit_input import DepositInput


def test_defaults(sample_deposit_input_params):
    deposit_input = DepositInput(**sample_deposit_input_params)

    assert deposit_input.pubkey == sample_deposit_input_params['pubkey']
