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
    block.slot == sample_beacon_block_params['slot']


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
