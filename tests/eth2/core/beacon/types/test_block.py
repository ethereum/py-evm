from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.blocks import BeaconBlock, BeaconBlockBody
from eth2.beacon.typing import FromBlockParams


def test_defaults(sample_beacon_block_params):
    block = BeaconBlock(**sample_beacon_block_params)
    assert block.slot == sample_beacon_block_params["slot"]
    assert block.is_genesis


def test_block_is_not_genesis(sample_beacon_block_params):
    genesis_block = BeaconBlock(**sample_beacon_block_params)
    another_block = BeaconBlock.from_parent(genesis_block, FromBlockParams())
    assert genesis_block.is_genesis
    assert not another_block.is_genesis


def test_update_attestations(sample_attestation_params, sample_beacon_block_params):
    block = BeaconBlock(**sample_beacon_block_params)
    attestations = block.body.attestations
    attestations = list(attestations)
    attestations.append(Attestation(**sample_attestation_params))
    body2 = block.body.copy(attestations=attestations)
    block2 = block.copy(body=body2)
    assert len(block2.body.attestations) == 1


def test_block_body_empty(sample_attestation_params):
    block_body = BeaconBlockBody()
    assert block_body.proposer_slashings == ()
    assert block_body.attester_slashings == ()
    assert block_body.attestations == ()
    assert block_body.deposits == ()
    assert block_body.voluntary_exits == ()
    assert block_body.transfers == ()

    assert block_body.is_empty

    block_body = block_body.copy(
        attestations=(Attestation(**sample_attestation_params),)
    )
    assert not block_body.is_empty


def test_block_root_and_block_header_root_equivalence(sample_block):
    block = sample_block
    header = block.header

    assert block.hash_tree_root == header.hash_tree_root
