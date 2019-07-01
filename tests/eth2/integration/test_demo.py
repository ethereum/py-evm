import pytest

from eth2.beacon.db.chain import BeaconChainDB
from eth2.beacon.fork_choice import higher_slot_scoring
from eth2.beacon.helpers import (
    slot_to_epoch,
)
from eth2.beacon.state_machines.forks.serenity.blocks import (
    SerenityBeaconBlock,
)
from eth2.beacon.state_machines.forks.serenity.configs import (
    SERENITY_CONFIG,
)
from eth2.beacon.state_machines.forks.serenity import (
    SerenityStateMachine,
)
from eth2.beacon.tools.builder.initializer import (
    create_mock_genesis,
)
from eth2.beacon.tools.builder.proposer import (
    create_mock_block,
)
from eth2.beacon.tools.builder.validator import (
    create_mock_signed_attestations_at_slot,
)
from eth2.beacon.tools.misc.ssz_vector import (
    override_vector_lengths,
)


#
# Mock bls verification for these tests
#
def mock_bls_verify(message_hash, pubkey, signature, domain):
    return True


def mock_bls_verify_multiple(pubkeys,
                             message_hashes,
                             signature,
                             domain):
    return True


@pytest.fixture(autouse=True)
def mock_bls(mocker, request):
    mocker.patch('py_ecc.bls.verify', side_effect=mock_bls_verify)
    mocker.patch('py_ecc.bls.verify_multiple', side_effect=mock_bls_verify_multiple)


@pytest.fixture
def fork_choice_scoring():
    return higher_slot_scoring


def test_demo(base_db,
              keymap,
              fork_choice_scoring):
    slots_per_epoch = 8
    config = SERENITY_CONFIG._replace(
        SLOTS_PER_EPOCH=slots_per_epoch,
        GENESIS_EPOCH=slot_to_epoch(SERENITY_CONFIG.GENESIS_SLOT, slots_per_epoch),
        TARGET_COMMITTEE_SIZE=3,
        SHARD_COUNT=2,
        MIN_ATTESTATION_INCLUSION_DELAY=2,
    )
    override_vector_lengths(config)
    fixture_sm_class = SerenityStateMachine.configure(
        __name__='SerenityStateMachineForTesting',
        config=config,
    )

    num_validators = 40

    genesis_slot = config.GENESIS_SLOT
    genesis_epoch = config.GENESIS_EPOCH
    chaindb = BeaconChainDB(base_db, config)

    genesis_state, genesis_block = create_mock_genesis(
        num_validators=num_validators,
        config=config,
        keymap=keymap,
        genesis_block_class=SerenityBeaconBlock,
    )
    for i in range(num_validators):
        assert genesis_state.validator_registry[i].is_active(genesis_slot)

    chaindb.persist_block(genesis_block, SerenityBeaconBlock, fork_choice_scoring)
    chaindb.persist_state(genesis_state)

    state = genesis_state
    block = genesis_block

    chain_length = 3 * config.SLOTS_PER_EPOCH
    blocks = (block,)

    attestations_map = {}  # Dict[Slot, Sequence[Attestation]]

    for current_slot in range(genesis_slot + 1, genesis_slot + chain_length + 1):
        if current_slot > genesis_slot + config.MIN_ATTESTATION_INCLUSION_DELAY:
            attestations = attestations_map[current_slot - config.MIN_ATTESTATION_INCLUSION_DELAY]
        else:
            attestations = ()

        block = create_mock_block(
            state=state,
            config=config,
            state_machine=fixture_sm_class(
                chaindb,
                blocks[-1].slot,
            ),
            block_class=SerenityBeaconBlock,
            parent_block=block,
            keymap=keymap,
            slot=current_slot,
            attestations=attestations,
        )

        # Get state machine instance
        sm = fixture_sm_class(
            chaindb,
            blocks[-1].slot,
        )
        state, _ = sm.import_block(block)

        chaindb.persist_state(state)
        chaindb.persist_block(block, SerenityBeaconBlock, fork_choice_scoring)

        blocks += (block,)

        # Mock attestations
        attestation_slot = current_slot
        attestations = create_mock_signed_attestations_at_slot(
            state=state,
            config=config,
            state_machine=fixture_sm_class(
                chaindb,
                block.slot,
            ),
            attestation_slot=attestation_slot,
            beacon_block_root=block.signing_root,
            keymap=keymap,
            voted_attesters_ratio=1.0,
        )
        attestations_map[attestation_slot] = attestations

    assert state.slot == chain_length + genesis_slot

    # Justification assertions
    assert state.current_justified_epoch == 2 + genesis_epoch
    assert state.finalized_epoch == 1 + genesis_epoch
