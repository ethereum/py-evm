import pytest
import rlp

from eth.beacon.types.blocks import (
    BaseBeaconBlock,
)
from eth.beacon.types.attestations import (
    Attestation,
)
from eth.utils.blake import (
    blake,
)


def test_defaults(sample_beacon_block_params):
    block = BaseBeaconBlock(**sample_beacon_block_params)
    assert block.slot == sample_beacon_block_params['slot']


def test_update_attestations(sample_attestation_params, sample_beacon_block_params):
    block = BaseBeaconBlock(**sample_beacon_block_params)
    attestations = block.body.attestations
    attestations = list(attestations)
    attestations.append(Attestation(**sample_attestation_params))
    body2 = block.body.copy(
        attestations=attestations
    )
    block2 = block.copy(
        body=body2
    )
    assert block2.num_attestations == 1


def test_hash(sample_beacon_block_params):
    block = BaseBeaconBlock(**sample_beacon_block_params)
    assert block.hash == blake(rlp.encode(block))


@pytest.mark.parametrize(
    'ancestor_hashes, parent_hash',
    [
        ((), None),
        ((b'\x01' * 32,), b'\x01' * 32),
        ((b'\x01' * 32, b'\x02' * 32), b'\x01' * 32)
    ]
)
def test_parent_hash(sample_beacon_block_params, ancestor_hashes, parent_hash):
    block = BaseBeaconBlock(**sample_beacon_block_params).copy(
        ancestor_hashes=ancestor_hashes,
    )
    assert block.parent_hash == parent_hash
