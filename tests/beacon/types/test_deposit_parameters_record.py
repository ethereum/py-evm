from eth.beacon.types.deposit_parameters_records import (
    DepositParametersRecord,
)


def test_defaults(sample_deposit_parameters_records_params):
    deposit_parameters_record = DepositParametersRecord(**sample_deposit_parameters_records_params)

    assert deposit_parameters_record.pubkey == sample_deposit_parameters_records_params['pubkey']
