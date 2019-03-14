import pytest

from eth2.beacon.db.chain import BeaconChainDB
from eth2.beacon.state_machines.forks.serenity.blocks import (
    SerenityBeaconBlock,
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


@pytest.mark.long
@pytest.mark.parametrize(
    (
        'num_validators,'
        'slots_per_epoch,'
        'min_attestation_inclusion_delay,'
        'target_committee_size,'
        'shard_count'
    ),
    [
        (40, 8, 2, 3, 2)
    ]
)
def test_demo(base_db,
              num_validators,
              config,
              keymap,
              fixture_sm_class):
    genesis_slot = config.GENESIS_SLOT
    genesis_epoch = config.GENESIS_EPOCH
    chaindb = BeaconChainDB(base_db)

    genesis_state, genesis_block = create_mock_genesis(
        num_validators=num_validators,
        config=config,
        keymap=keymap,
        genesis_block_class=SerenityBeaconBlock,
    )
    for i in range(num_validators):
        assert genesis_state.validator_registry[i].is_active(genesis_slot)

    chaindb.persist_block(genesis_block, SerenityBeaconBlock)
    chaindb.persist_state(genesis_state)

    state = genesis_state
    block = genesis_block

    chain_length = 3 * config.SLOTS_PER_EPOCH
    blocks = (block,)

    attestations_map = {}  # Dict[Slot, Sequence[Attestation]]

    for current_slot in range(genesis_slot + 1, genesis_slot + chain_length):
        if current_slot > genesis_slot + config.MIN_ATTESTATION_INCLUSION_DELAY:
            attestations = attestations_map[current_slot - config.MIN_ATTESTATION_INCLUSION_DELAY]
        else:
            attestations = ()

        block = create_mock_block(
            state=state,
            config=config,
            state_machine=fixture_sm_class(
                chaindb,
                blocks[-1],
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
            blocks[-1],
        )
        state, _ = sm.import_block(block)

        chaindb.persist_state(state)
        chaindb.persist_block(block, SerenityBeaconBlock)

        blocks += (block,)

        # Mock attestations
        attestation_slot = current_slot
        attestations = create_mock_signed_attestations_at_slot(
            state=state,
            config=config,
            attestation_slot=attestation_slot,
            beacon_block_root=block.root,
            keymap=keymap,
            voted_attesters_ratio=1.0,
        )
        attestations_map[attestation_slot] = attestations

    assert state.slot == chain_length - 1 + genesis_slot
    assert isinstance(sm.block, SerenityBeaconBlock)

    # Justification assertions
    assert state.justified_epoch == 2 + genesis_epoch
    assert state.finalized_epoch == 1 + genesis_epoch
