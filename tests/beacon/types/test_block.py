import pytest
import rlp

from eth.beacon.types.blocks import (
    BaseBeaconBlock,
)
from eth.beacon.types.attestation_records import (
    AttestationRecord,
)
from eth.utils.blake import (
    blake,
)


def test_defaults(sample_beacon_block_params):
    block = BaseBeaconBlock(**sample_beacon_block_params)
    assert block.slot == sample_beacon_block_params['slot']


def test_update_attestations(sample_attestation_record_params, sample_beacon_block_params):
    block = BaseBeaconBlock(**sample_beacon_block_params)
    attestations = block.attestations
    attestations = list(attestations)
    attestations.append(AttestationRecord(**sample_attestation_record_params))
    block2 = block.copy(
        attestations=attestations
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
