from eth_utils import ValidationError
import pytest

from eth2.beacon.helpers import compute_start_slot_at_epoch
from eth2.beacon.state_machines.forks.serenity.block_validation import (
    _validate_attestation_data,
    validate_attestation_slot,
)
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.checkpoints import Checkpoint


@pytest.mark.parametrize(
    ("slots_per_epoch", "min_attestation_inclusion_delay"), [(4, 2)]
)
@pytest.mark.parametrize(
    ("attestation_slot," "state_slot," "is_valid,"),
    [
        # in bounds at lower end
        (8, 2 + 8, True),
        # in bounds at high end
        (8, 8 + 4, True),
        # state_slot > attestation_slot + slots_per_epoch
        (8, 8 + 4 + 1, False),
        # attestation_slot + min_attestation_inclusion_delay > state_slot
        (8, 8 - 2, False),
    ],
)
def test_validate_attestation_slot(
    attestation_slot,
    state_slot,
    slots_per_epoch,
    min_attestation_inclusion_delay,
    is_valid,
):

    if is_valid:
        validate_attestation_slot(
            attestation_slot,
            state_slot,
            slots_per_epoch,
            min_attestation_inclusion_delay,
        )
    else:
        with pytest.raises(ValidationError):
            validate_attestation_slot(
                attestation_slot,
                state_slot,
                slots_per_epoch,
                min_attestation_inclusion_delay,
            )


@pytest.mark.parametrize(
    (
        "current_epoch",
        "previous_justified_epoch",
        "current_justified_epoch",
        "slots_per_epoch",
    ),
    [(3, 1, 2, 8)],
)
@pytest.mark.parametrize(
    ("attestation_source_epoch", "attestation_target_epoch", "is_valid"),
    [
        (2, 3, True),
        # wrong target_epoch
        (0, 1, False),
        # wrong source checkpoint
        (1, 3, False),
    ],
)
def test_validate_attestation_data(
    genesis_state,
    sample_attestation_data_params,
    attestation_source_epoch,
    attestation_target_epoch,
    current_epoch,
    previous_justified_epoch,
    current_justified_epoch,
    slots_per_epoch,
    config,
    is_valid,
):
    state = genesis_state.copy(
        slot=compute_start_slot_at_epoch(current_epoch, slots_per_epoch) + 5,
        previous_justified_checkpoint=Checkpoint(epoch=previous_justified_epoch),
        current_justified_checkpoint=Checkpoint(epoch=current_justified_epoch),
    )
    target_slot = compute_start_slot_at_epoch(current_epoch, config.SLOTS_PER_EPOCH)
    committee_index = 0

    attestation_data = AttestationData(**sample_attestation_data_params).copy(
        slot=target_slot,
        index=committee_index,
        source=Checkpoint(epoch=attestation_source_epoch),
        target=Checkpoint(epoch=attestation_target_epoch),
    )

    if is_valid:
        _validate_attestation_data(state, attestation_data, config)
    else:
        with pytest.raises(ValidationError):
            _validate_attestation_data(state, attestation_data, config)
