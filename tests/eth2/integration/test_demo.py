import pytest

from eth2._utils.bls import bls
from eth2.beacon.db.chain import BeaconChainDB
from eth2.beacon.fork_choice.higher_slot import higher_slot_scoring
from eth2.beacon.helpers import compute_epoch_of_slot
from eth2.beacon.operations.attestation_pool import AttestationPool
from eth2.beacon.state_machines.forks.serenity import SerenityStateMachine
from eth2.beacon.state_machines.forks.serenity.blocks import SerenityBeaconBlock
from eth2.beacon.state_machines.forks.serenity.configs import SERENITY_CONFIG
from eth2.beacon.tools.builder.initializer import create_mock_genesis
from eth2.beacon.tools.builder.proposer import create_mock_block
from eth2.beacon.tools.builder.validator import create_mock_signed_attestations_at_slot
from eth2.beacon.tools.misc.ssz_vector import override_lengths


@pytest.fixture
def fork_choice_scoring():
    return higher_slot_scoring


@pytest.mark.parametrize(("validator_count"), ((40),))
def test_demo(base_db, validator_count, keymap, pubkeys, fork_choice_scoring):
    bls.use_noop_backend()
    slots_per_epoch = 8
    config = SERENITY_CONFIG._replace(
        SLOTS_PER_EPOCH=slots_per_epoch,
        GENESIS_EPOCH=compute_epoch_of_slot(
            SERENITY_CONFIG.GENESIS_SLOT, slots_per_epoch
        ),
        TARGET_COMMITTEE_SIZE=3,
        SHARD_COUNT=2,
        MIN_ATTESTATION_INCLUSION_DELAY=2,
    )
    override_lengths(config)
    fixture_sm_class = SerenityStateMachine.configure(
        __name__="SerenityStateMachineForTesting", config=config
    )

    genesis_slot = config.GENESIS_SLOT
    genesis_epoch = config.GENESIS_EPOCH
    chaindb = BeaconChainDB(base_db, config)
    attestation_pool = AttestationPool()

    genesis_state, genesis_block = create_mock_genesis(
        pubkeys=pubkeys[:validator_count],
        config=config,
        keymap=keymap,
        genesis_block_class=SerenityBeaconBlock,
    )
    for i in range(validator_count):
        assert genesis_state.validators[i].is_active(genesis_slot)

    chaindb.persist_block(genesis_block, SerenityBeaconBlock, fork_choice_scoring)
    chaindb.persist_state(genesis_state)

    state = genesis_state
    block = genesis_block

    chain_length = 3 * config.SLOTS_PER_EPOCH
    blocks = (block,)

    attestations_map = {}  # Dict[Slot, Sequence[Attestation]]

    for current_slot in range(genesis_slot + 1, genesis_slot + chain_length + 1):
        if current_slot > genesis_slot + config.MIN_ATTESTATION_INCLUSION_DELAY:
            attestations = attestations_map[
                current_slot - config.MIN_ATTESTATION_INCLUSION_DELAY
            ]
        else:
            attestations = ()

        block = create_mock_block(
            state=state,
            config=config,
            state_machine=fixture_sm_class(chaindb, attestation_pool, blocks[-1].slot),
            block_class=SerenityBeaconBlock,
            parent_block=block,
            keymap=keymap,
            slot=current_slot,
            attestations=attestations,
        )

        # Get state machine instance
        sm = fixture_sm_class(chaindb, attestation_pool, blocks[-1].slot)
        state, _ = sm.import_block(block, state)

        chaindb.persist_state(state)
        chaindb.persist_block(block, SerenityBeaconBlock, fork_choice_scoring)

        blocks += (block,)

        # Mock attestations
        attestation_slot = current_slot
        attestations = create_mock_signed_attestations_at_slot(
            state=state,
            config=config,
            state_machine=fixture_sm_class(chaindb, attestation_pool, block.slot),
            attestation_slot=attestation_slot,
            beacon_block_root=block.signing_root,
            keymap=keymap,
            voted_attesters_ratio=1.0,
        )
        attestations_map[attestation_slot] = attestations

    assert state.slot == chain_length + genesis_slot

    # Justification assertions
    assert state.current_justified_checkpoint.epoch == genesis_epoch
    assert state.finalized_checkpoint.epoch == genesis_epoch
