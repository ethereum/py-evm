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
)
from eth2.beacon.tools.builder.validator import (
    create_mock_signed_attestations_at_slot,
    create_mock_proposer_slashing_at_block,
)


def test_process_max_attestations(genesis_state,
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
        state,
        config,
        attestation_slot,
        keymap,
        1.0,
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
        'epoch_length',
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
        'num_validators,'
        'epoch_length,'
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
        state,
        config,
        attestation_slot,
        keymap,
        1.0,
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
