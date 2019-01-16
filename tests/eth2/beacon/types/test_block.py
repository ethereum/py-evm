from eth2.beacon.types.attestations import (
    Attestation,
)
from eth2.beacon.types.blocks import (
    BeaconBlock,
    BeaconBlockBody,
)


def test_defaults(sample_beacon_block_params):
    block = BeaconBlock(**sample_beacon_block_params)
    assert block.slot == sample_beacon_block_params['slot']
    assert len(block.body.custody_challenges) == 0


def test_update_attestations(sample_attestation_params, sample_beacon_block_params):
    block = BeaconBlock(**sample_beacon_block_params)
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


def test_block_body_empty(sample_attestation_params):
    block_body = BeaconBlockBody.create_empty_body()
    assert block_body.proposer_slashings == ()
    assert block_body.casper_slashings == ()
    assert block_body.attestations == ()
    assert block_body.custody_reseeds == ()
    assert block_body.custody_challenges == ()
    assert block_body.custody_responses == ()
    assert block_body.deposits == ()
    assert block_body.exits == ()

    assert block_body.is_empty

    block_body = block_body.copy(
        attestations=(Attestation(**sample_attestation_params),),
    )
    assert not block_body.is_empty
