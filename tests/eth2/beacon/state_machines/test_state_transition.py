import pytest

from eth2.beacon.db.chain import BeaconChainDB
from eth2.beacon.helpers import get_beacon_proposer_index
from eth2.beacon.state_machines.forks.serenity.blocks import (
    SerenityBeaconBlock,
)
from eth2.beacon.tools.builder.proposer import (
    create_mock_block,
)

from eth2._utils.merkle import get_merkle_root


@pytest.mark.parametrize(
    (
        'num_validators,'
        'epoch_length,'
        'min_attestation_inclusion_delay,'
        'target_committee_size,'
        'shard_count,'
        'state_slot,'
        'latest_block_roots_length'
    ),
    [
        (10, 10, 1, 2, 2, 2, 8192),
        # state.slot == LATEST_BLOCK_ROOTS_LENGTH
        (6, 6, 1, 2, 2, 5, 5),
        # state.slot > LATEST_BLOCK_ROOTS_LENGTH
        (7, 7, 1, 2, 2, 6, 5),
        # state.slot < LATEST_BLOCK_ROOTS_LENGTH
        (7, 7, 1, 2, 2, 3, 5),
        # state.slot % LATEST_BLOCK_ROOTS_LENGTH = 0
        (11, 11, 1, 2, 2, 10, 5),
        (16, 16, 1, 2, 2, 15, 5),
        # updated_state.slot == LATEST_BLOCK_ROOTS_LENGTH
        (6, 6, 1, 2, 2, 4, 5),
        # updated_state.slot % LATEST_BLOCK_ROOTS_LENGTH = 0
        (6, 6, 1, 2, 2, 5, 5),
        (11, 11, 1, 2, 2, 9, 5),
        (16, 16, 1, 2, 2, 14, 5),
    ]
)
def test_per_slot_transition(base_db,
                             genesis_block,
                             genesis_state,
                             fixture_sm_class,
                             config,
                             state_slot,
                             keymap):
    chaindb = BeaconChainDB(base_db)
    chaindb.persist_block(genesis_block, SerenityBeaconBlock)
    chaindb.persist_state(genesis_state)

    state = genesis_state

    block = create_mock_block(
        state=state,
        config=config,
        block_class=SerenityBeaconBlock,
        parent_block=genesis_block,
        keymap=keymap,
        slot=state_slot,
    )

    # Store in chaindb
    chaindb.persist_block(block, SerenityBeaconBlock)

    # Get state machine instance
    sm = fixture_sm_class(
        chaindb,
        block,
        parent_block_class=SerenityBeaconBlock,
    )

    # Get state transition instance
    st = sm.state_transition_class(sm.config)

    updated_state = st.per_slot_transition(state, block.parent_root)

    # Ensure that slot gets increased by 1
    assert updated_state.slot == state.slot + 1

    # Validator Registry
    # Tweaking the slot, so that we get the correct proposer index
    beacon_proposer_index = get_beacon_proposer_index(
        state,
        state.slot + 1,
        st.config.EPOCH_LENGTH,
        st.config.TARGET_COMMITTEE_SIZE,
        st.config.SHARD_COUNT,
    )
    for validator_index, _ in enumerate(updated_state.validator_registry):
        if validator_index != beacon_proposer_index:
            # Validator Record shouldn't change if not proposer
            assert (
                updated_state.validator_registry[validator_index] ==
                state.validator_registry[validator_index]
            )
        else:
            # randao layers of proposer's record should increase by 1
            assert (
                updated_state.validator_registry[validator_index].randao_layers ==
                state.validator_registry[validator_index].randao_layers + 1
            )

    # latest_randao_mixes
    assert (
        updated_state.latest_randao_mixes[
            updated_state.slot % st.config.LATEST_RANDAO_MIXES_LENGTH
        ] == state.latest_randao_mixes[(state.slot) % st.config.LATEST_RANDAO_MIXES_LENGTH]
    )

    # latest_block_roots
    latest_block_roots_index = (updated_state.slot - 1) % st.config.LATEST_BLOCK_ROOTS_LENGTH
    assert updated_state.latest_block_roots[latest_block_roots_index] == block.parent_root

    # batched_block_roots
    if updated_state.slot % st.config.LATEST_BLOCK_ROOTS_LENGTH == 0:
        assert updated_state.batched_block_roots[-1] == get_merkle_root(
            updated_state.latest_block_roots
        )
    else:
        assert updated_state.batched_block_roots == state.batched_block_roots
