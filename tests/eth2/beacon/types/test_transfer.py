import ssz

from eth2.beacon.types.transfers import (
    Transfer,
)


def test_defaults(sample_transfer_params):
    transfer = Transfer(**sample_transfer_params)

    assert transfer.to_validator_index == sample_transfer_params['to_validator_index']
    assert ssz.encode(transfer)
