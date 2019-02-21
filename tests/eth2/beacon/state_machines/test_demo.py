import pytest

from eth2.beacon.configs import CommitteeConfig
from eth2.beacon.committee_helpers import get_beacon_proposer_index

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


@pytest.mark.parametrize(
    (
        'num_validators,'
        'slots_per_epoch,'
        'min_attestation_inclusion_delay,'
        'target_committee_size,'
        'shard_count,'
    ),
    [
        (20, 4, 2, 5, 4)
    ]
)
def test_demo(base_db,
              num_validators,
              config,
              keymap,
              fixture_sm_class):
    chaindb = BeaconChainDB(base_db)

    genesis_state, genesis_block = create_mock_genesis(
        num_validators=num_validators,
        config=config,
        keymap=keymap,
        genesis_block_class=SerenityBeaconBlock,
    )
    for i in range(num_validators):
        assert genesis_state.validator_registry[i].is_active(0)

    chaindb.persist_block(genesis_block, SerenityBeaconBlock)
    chaindb.persist_state(genesis_state)

    state = genesis_state
    block = genesis_block

    chain_length = 5 * config.SLOTS_PER_EPOCH
    attestations = ()
    blocks = (block,)
    for current_slot in range(chain_length):
        # two epochs
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
        block = block.copy(
            body=block.body.copy(
                attestations=attestations,
            )
        )

        proposer_index = get_beacon_proposer_index(
            state.copy(
                slot=current_slot,
            ),
            current_slot,
            CommitteeConfig(config),
        )
        proposer_balance = state.validator_balances[proposer_index]

        # Get state machine instance
        sm = fixture_sm_class(
            chaindb,
            blocks[-1],
        )
        state, _ = sm.import_block(block)

        # Check if proposer balance is increased after epoch transition
        is_first_epoch = state.current_epoch(config.EPOCH_LENGTH) == 0
        is_end_of_epoch = (current_slot + 1) % config.EPOCH_LENGTH == 0
        if not is_first_epoch and is_end_of_epoch:
            proposer_balance_after_epoch_processing = state.validator_balances[proposer_index]
            assert proposer_balance_after_epoch_processing > proposer_balance

        chaindb.persist_state(state)
        chaindb.persist_block(block, SerenityBeaconBlock)

        blocks += (block,)
        if current_slot >= config.MIN_ATTESTATION_INCLUSION_DELAY:
            attestation_slot = current_slot - config.MIN_ATTESTATION_INCLUSION_DELAY
            is_attestation_in_prev_epoch = (
                attestation_slot // config.EPOCH_LENGTH < state.current_epoch(config.EPOCH_LENGTH)
            )
            # epoch transition will change `justified_epoch` so if epoch transition took place,
            # `attestation.data.justified_epoch` should be set to `state.previous_justified_epoch`
            is_state_after_epoch_processing = (current_slot + 1) % config.EPOCH_LENGTH == 0
            if is_attestation_in_prev_epoch or is_state_after_epoch_processing:
                justified_epoch = state.previous_justified_epoch
            else:
                justified_epoch = state.justified_epoch
            attestations = create_mock_signed_attestations_at_slot(
                state,
                config,
                attestation_slot,
                justified_epoch,
                keymap,
                1.0,
            )
        else:
            attestations = ()

    assert state.slot == chain_length - 1
    assert isinstance(sm.block, SerenityBeaconBlock)
