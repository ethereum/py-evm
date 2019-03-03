import pytest

from eth_utils import (
    ValidationError,
)

from eth2.beacon.types.blocks import (
    BeaconBlockBody,
)
from eth2.beacon.state_machines.forks.serenity.blocks import (
    SerenityBeaconBlock,
)
from eth2.beacon.state_machines.forks.serenity.operation_processing import (
    process_attestations,
    process_proposer_slashings,
    process_attester_slashings,
    process_voluntary_exits,
)
from eth2.beacon.tools.builder.validator import (
    create_mock_attester_slashing_is_double_vote,
    create_mock_signed_attestations_at_slot,
    create_mock_proposer_slashing_at_block,
    create_mock_voluntary_exit,
)


def test_process_max_attestations(genesis_state,
                                  genesis_block,
                                  sample_beacon_block_params,
                                  sample_beacon_block_body_params,
                                  config,
                                  keymap):
    attestation_slot = 0
    current_slot = attestation_slot + config.MIN_ATTESTATION_INCLUSION_DELAY
    state = genesis_state.copy(
        slot=current_slot,
    )

    attestations = create_mock_signed_attestations_at_slot(
        state=state,
        config=config,
        attestation_slot=attestation_slot,
        beacon_block_root=genesis_block.root,
        keymap=keymap,
        voted_attesters_ratio=1.0,
    )

    attestations_count = len(attestations)
    assert attestations_count > 0

    block_body = BeaconBlockBody(**sample_beacon_block_body_params).copy(
        attestations=attestations * (attestations_count // config.MAX_ATTESTATIONS + 1),
    )
    block = SerenityBeaconBlock(**sample_beacon_block_params).copy(
        slot=current_slot,
        body=block_body,
    )

    with pytest.raises(ValidationError):
        process_attestations(
            state,
            block,
            config,
        )


@pytest.mark.parametrize(
    (
        'num_validators',
        'slots_per_epoch',
        'target_committee_size',
        'shard_count',
        'block_root_1',
        'block_root_2',
        'success'
    ),
    [
        (10, 2, 2, 2, b'\x11' * 32, b'\x22' * 32, True),
        (10, 2, 2, 2, b'\x11' * 32, b'\x11' * 32, False),
    ]
)
def test_process_proposer_slashings(genesis_state,
                                    sample_beacon_block_params,
                                    sample_beacon_block_body_params,
                                    config,
                                    keymap,
                                    block_root_1,
                                    block_root_2,
                                    success):
    current_slot = 1
    state = genesis_state.copy(
        slot=current_slot,
    )

    proposer_index = 0
    proposer_slashing = create_mock_proposer_slashing_at_block(
        state,
        config,
        keymap,
        block_root_1=block_root_1,
        block_root_2=block_root_2,
        proposer_index=proposer_index,
    )
    proposer_slashings = (proposer_slashing,)

    block_body = BeaconBlockBody(**sample_beacon_block_body_params).copy(
        proposer_slashings=proposer_slashings,
    )
    block = SerenityBeaconBlock(**sample_beacon_block_params).copy(
        slot=current_slot,
        body=block_body,
    )

    if success:
        new_state = process_proposer_slashings(
            state,
            block,
            config,
        )
        # Check if slashed
        assert (
            new_state.validator_balances[proposer_index] < state.validator_balances[proposer_index]
        )
    else:
        with pytest.raises(ValidationError):
            process_proposer_slashings(
                state,
                block,
                config,
            )


@pytest.mark.parametrize(
    (
        'num_validators',
        'slots_per_epoch',
        'target_committee_size',
        'shard_count',
        'min_attestation_inclusion_delay',
    ),
    [
        (100, 2, 2, 2, 1),
    ]
)
@pytest.mark.parametrize(
    ('success'),
    [
        # (True),
        (False),
    ]
)
def test_process_attester_slashings(genesis_state,
                                    sample_beacon_block_params,
                                    sample_beacon_block_body_params,
                                    config,
                                    keymap,
                                    min_attestation_inclusion_delay,
                                    success):
    attesting_state = genesis_state.copy(
        slot=genesis_state.slot + config.SLOTS_PER_EPOCH,
    )
    valid_attester_slashing = create_mock_attester_slashing_is_double_vote(
        attesting_state,
        config,
        keymap,
        attestation_epoch=0,
    )
    state = attesting_state.copy(
        slot=attesting_state.slot + min_attestation_inclusion_delay,
    )

    if success:
        block_body = BeaconBlockBody(**sample_beacon_block_body_params).copy(
            attester_slashings=(valid_attester_slashing,),
        )
        block = SerenityBeaconBlock(**sample_beacon_block_params).copy(
            slot=state.slot,
            body=block_body,
        )

        attester_index = valid_attester_slashing.slashable_attestation_1.validator_indices[0]

        new_state = process_attester_slashings(
            state,
            block,
            config,
        )
        # Check if slashed
        assert (
            new_state.validator_balances[attester_index] < state.validator_balances[attester_index]
        )
    else:
        invalid_attester_slashing = valid_attester_slashing.copy(
            slashable_attestation_2=valid_attester_slashing.slashable_attestation_2.copy(
                data=valid_attester_slashing.slashable_attestation_1.data,
            )
        )
        block_body = BeaconBlockBody(**sample_beacon_block_body_params).copy(
            attester_slashings=(invalid_attester_slashing,),
        )
        block = SerenityBeaconBlock(**sample_beacon_block_params).copy(
            slot=state.slot,
            body=block_body,
        )

        with pytest.raises(ValidationError):
            process_attester_slashings(
                state,
                block,
                config,
            )


@pytest.mark.parametrize(
    (
        'num_validators,'
        'slots_per_epoch,'
        'min_attestation_inclusion_delay,'
        'target_committee_size,'
        'shard_count,'
        'success,'
    ),
    [
        (10, 2, 1, 2, 2, True),
        (10, 2, 1, 2, 2, False),
        (40, 4, 2, 3, 5, True),
    ]
)
def test_process_attestations(genesis_state,
                              genesis_block,
                              sample_beacon_block_params,
                              sample_beacon_block_body_params,
                              config,
                              keymap,
                              success):

    attestation_slot = 0
    current_slot = attestation_slot + config.MIN_ATTESTATION_INCLUSION_DELAY
    state = genesis_state.copy(
        slot=current_slot,
    )

    attestations = create_mock_signed_attestations_at_slot(
        state=state,
        config=config,
        attestation_slot=attestation_slot,
        beacon_block_root=genesis_block.root,
        keymap=keymap,
        voted_attesters_ratio=1.0,
    )

    assert len(attestations) > 0

    if not success:
        # create invalid attestation in the future
        invalid_attestation_data = attestations[-1].data.copy(
            slot=state.slot + 10,
        )
        invalid_attestation = attestations[-1].copy(
            data=invalid_attestation_data,
        )
        attestations = attestations[:-1] + (invalid_attestation,)

    block_body = BeaconBlockBody(**sample_beacon_block_body_params).copy(
        attestations=attestations,
    )
    block = SerenityBeaconBlock(**sample_beacon_block_params).copy(
        slot=current_slot,
        body=block_body,
    )

    if success:
        new_state = process_attestations(
            state,
            block,
            config,
        )

        assert len(new_state.latest_attestations) == len(attestations)
    else:
        with pytest.raises(ValidationError):
            process_attestations(
                state,
                block,
                config,
            )


@pytest.mark.parametrize(
    (
        'num_validators',
        'slots_per_epoch',
        'target_committee_size',
        'activation_exit_delay',
    ),
    [
        (40, 2, 2, 2),
    ]
)
@pytest.mark.parametrize(
    (
        'success',
    ),
    [
        (True,),
        (False,),
    ]
)
def test_process_voluntary_exits(genesis_state,
                                 sample_beacon_block_params,
                                 sample_beacon_block_body_params,
                                 config,
                                 keymap,
                                 min_attestation_inclusion_delay,
                                 success):
    state = genesis_state
    validator_index = 0
    valid_voluntary_exit = create_mock_voluntary_exit(
        state,
        config,
        keymap,
        validator_index,
    )

    if success:
        block_body = BeaconBlockBody(**sample_beacon_block_body_params).copy(
            voluntary_exits=(valid_voluntary_exit,),
        )
        block = SerenityBeaconBlock(**sample_beacon_block_params).copy(
            slot=state.slot,
            body=block_body,
        )

        new_state = process_voluntary_exits(
            state,
            block,
            config,
        )
        # Check if initiated exit
        assert (
            new_state.validator_registry[validator_index].initiated_exit
        )
    else:
        invalid_voluntary_exit = valid_voluntary_exit.copy(
            signature=b'\x12' * 96,  # Put wrong signature
        )
        block_body = BeaconBlockBody(**sample_beacon_block_body_params).copy(
            voluntary_exits=(invalid_voluntary_exit,),
        )
        block = SerenityBeaconBlock(**sample_beacon_block_params).copy(
            slot=state.slot,
            body=block_body,
        )

        with pytest.raises(ValidationError):
            process_voluntary_exits(
                state,
                block,
                config,
            )
