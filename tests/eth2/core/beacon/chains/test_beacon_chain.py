import copy

import pytest

from eth2.beacon.chains.base import BeaconChain
from eth2.beacon.db.exceptions import AttestationRootNotFound, StateNotFound
from eth2.beacon.exceptions import BlockClassError
from eth2.beacon.state_machines.forks.serenity.blocks import SerenityBeaconBlock
from eth2.beacon.tools.builder.proposer import create_mock_block
from eth2.beacon.tools.builder.validator import create_mock_signed_attestations_at_slot
from eth2.beacon.types.blocks import BeaconBlock


@pytest.fixture
def chain(beacon_chain_without_block_validation):
    return beacon_chain_without_block_validation


@pytest.fixture
def valid_chain(beacon_chain_with_block_validation):
    return beacon_chain_with_block_validation


@pytest.mark.parametrize(
    ("validator_count,slots_per_epoch,target_committee_size,shard_count"),
    [(100, 20, 10, 20)],
)
def test_canonical_chain(valid_chain, genesis_slot, fork_choice_scoring):
    genesis_block = valid_chain.get_canonical_block_by_slot(genesis_slot)

    # Our chain fixture is created with only the genesis header, so initially that's the head of
    # the canonical chain.
    assert valid_chain.get_canonical_head() == genesis_block
    # verify a special case (score(genesis) == 0)
    assert valid_chain.get_score(genesis_block.signing_root) == 0

    block = genesis_block.copy(
        slot=genesis_block.slot + 1, parent_root=genesis_block.signing_root
    )
    valid_chain.chaindb.persist_block(block, block.__class__, fork_choice_scoring)

    assert valid_chain.get_canonical_head() == block
    state_machine = valid_chain.get_state_machine(block.slot)
    scoring_fn = state_machine.get_fork_choice_scoring()

    assert valid_chain.get_score(block.signing_root) == scoring_fn(block)
    assert scoring_fn(block) != 0

    canonical_block_1 = valid_chain.get_canonical_block_by_slot(genesis_block.slot + 1)
    assert canonical_block_1 == block

    result_block = valid_chain.get_block_by_root(block.signing_root)
    assert result_block == block


@pytest.mark.parametrize(
    ("validator_count," "slots_per_epoch," "target_committee_size," "shard_count,"),
    [(100, 16, 10, 16)],
)
def test_get_state_by_slot(valid_chain, genesis_block, genesis_state, config, keymap):
    # Fisrt, skip block and check if `get_state_by_slot` returns the expected state
    state_machine = valid_chain.get_state_machine(genesis_block.slot)
    state = valid_chain.get_head_state()
    block_skipped_slot = genesis_block.slot + 1
    block_skipped_state = state_machine.state_transition.apply_state_transition(
        state, future_slot=block_skipped_slot
    )
    with pytest.raises(StateNotFound):
        valid_chain.get_state_by_slot(block_skipped_slot)
    valid_chain.chaindb.persist_state(block_skipped_state)
    assert (
        valid_chain.get_state_by_slot(block_skipped_slot).hash_tree_root
        == block_skipped_state.hash_tree_root
    )

    # Next, import proposed block and check if `get_state_by_slot` returns the expected state
    proposed_slot = block_skipped_slot + 1
    block = create_mock_block(
        state=block_skipped_state,
        config=config,
        state_machine=state_machine,
        block_class=genesis_block.__class__,
        parent_block=genesis_block,
        keymap=keymap,
        slot=proposed_slot,
        attestations=(),
    )
    valid_chain.import_block(block)
    state = valid_chain.get_head_state()
    assert (
        valid_chain.get_state_by_slot(proposed_slot).hash_tree_root
        == state.hash_tree_root
    )


@pytest.mark.long
@pytest.mark.parametrize(
    ("validator_count,slots_per_epoch,target_committee_size,shard_count"),
    [(100, 16, 10, 16)],
)
def test_import_blocks(valid_chain, genesis_block, genesis_state, config, keymap):
    state = genesis_state
    blocks = (genesis_block,)
    valid_chain_2 = copy.deepcopy(valid_chain)
    for _ in range(3):
        block = create_mock_block(
            state=state,
            config=config,
            state_machine=valid_chain.get_state_machine(blocks[-1].slot),
            block_class=genesis_block.__class__,
            parent_block=blocks[-1],
            keymap=keymap,
            slot=state.slot + 2,
        )

        valid_chain.import_block(block)
        assert valid_chain.get_canonical_head() == block

        state = valid_chain.get_state_by_slot(block.slot)

        assert block == valid_chain.get_canonical_block_by_slot(block.slot)
        assert block.signing_root == valid_chain.get_canonical_block_root(block.slot)
        blocks += (block,)

    assert valid_chain.get_canonical_head() != valid_chain_2.get_canonical_head()

    for block in blocks[1:]:
        valid_chain_2.import_block(block)

    assert valid_chain.get_canonical_head() == valid_chain_2.get_canonical_head()
    assert valid_chain.get_state_by_slot(blocks[-1].slot).slot != 0
    assert valid_chain.get_state_by_slot(
        blocks[-1].slot
    ) == valid_chain_2.get_state_by_slot(blocks[-1].slot)


def test_from_genesis(base_db, genesis_block, genesis_state, fixture_sm_class, config):
    klass = BeaconChain.configure(
        __name__="TestChain", sm_configuration=((0, fixture_sm_class),), chain_id=5566
    )

    assert type(genesis_block) == SerenityBeaconBlock
    block = BeaconBlock.convert_block(genesis_block)
    assert type(block) == BeaconBlock

    with pytest.raises(BlockClassError):
        klass.from_genesis(base_db, genesis_state, block, config)


@pytest.mark.long
@pytest.mark.parametrize(
    (
        "validator_count,"
        "slots_per_epoch,"
        "target_committee_size,"
        "shard_count,"
        "min_attestation_inclusion_delay,"
    ),
    [(100, 16, 10, 16, 0)],
)
def test_get_attestation_root(
    valid_chain,
    genesis_block,
    genesis_state,
    config,
    keymap,
    min_attestation_inclusion_delay,
):
    state_machine = valid_chain.get_state_machine()
    attestations = create_mock_signed_attestations_at_slot(
        state=genesis_state,
        config=config,
        state_machine=state_machine,
        attestation_slot=genesis_block.slot,
        beacon_block_root=genesis_block.signing_root,
        keymap=keymap,
    )
    block = create_mock_block(
        state=genesis_state,
        config=config,
        state_machine=state_machine,
        block_class=genesis_block.__class__,
        parent_block=genesis_block,
        keymap=keymap,
        slot=genesis_state.slot + 1,
        attestations=attestations,
    )
    valid_chain.import_block(block)
    # Only one attestation in attestations, so just check that one
    a0 = attestations[0]
    assert valid_chain.get_attestation_by_root(a0.hash_tree_root) == a0
    assert valid_chain.attestation_exists(a0.hash_tree_root)
    fake_attestation = a0.copy(signature=b"\x78" * 96)
    with pytest.raises(AttestationRootNotFound):
        valid_chain.get_attestation_by_root(fake_attestation.hash_tree_root)
    assert not valid_chain.attestation_exists(fake_attestation.hash_tree_root)
