import ssz

from eth2.beacon.types.exits import (
    Exit,
)


def test_defaults(sample_exit_params):
    exit = Exit(**sample_exit_params)

    assert exit.signature[0] == sample_exit_params['signature'][0]
    assert ssz.encode(exit)
