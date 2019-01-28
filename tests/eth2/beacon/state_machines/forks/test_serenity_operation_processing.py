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
)
from eth2.beacon.tools.builder.validator import (
    create_mock_signed_attestations_at_slot,
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
