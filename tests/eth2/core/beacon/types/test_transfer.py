import ssz

from eth2.beacon.types.transfers import Transfer


def test_defaults(sample_transfer_params):
    transfer = Transfer(**sample_transfer_params)

    assert transfer.recipient == sample_transfer_params["recipient"]
    assert ssz.encode(transfer)
