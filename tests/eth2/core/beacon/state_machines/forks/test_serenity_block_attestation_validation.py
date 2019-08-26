from eth.constants import ZERO_HASH32
from eth_utils import ValidationError
import pytest

from eth2.beacon.committee_helpers import get_start_shard
from eth2.beacon.helpers import compute_start_slot_of_epoch
from eth2.beacon.state_machines.forks.serenity.block_validation import (
    _validate_attestation_data,
    _validate_crosslink,
    validate_attestation_slot,
)
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.checkpoints import Checkpoint
from eth2.beacon.types.crosslinks import Crosslink
from eth2.configs import CommitteeConfig


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
        slot=compute_start_slot_of_epoch(current_epoch, slots_per_epoch) + 5,
        previous_justified_checkpoint=Checkpoint(epoch=previous_justified_epoch),
        current_justified_checkpoint=Checkpoint(epoch=current_justified_epoch),
    )
    start_shard = get_start_shard(state, current_epoch, CommitteeConfig(config))
    if attestation_target_epoch == current_epoch:
        crosslinks = state.current_crosslinks
    else:
        crosslinks = state.previous_crosslinks

    parent_crosslink = crosslinks[start_shard]
    attestation_data = AttestationData(**sample_attestation_data_params).copy(
        source=Checkpoint(epoch=attestation_source_epoch),
        target=Checkpoint(epoch=attestation_target_epoch),
        crosslink=Crosslink(
            start_epoch=parent_crosslink.end_epoch,
            end_epoch=attestation_target_epoch,
            parent_root=parent_crosslink.hash_tree_root,
            shard=start_shard,
        ),
    )

    if is_valid:
        _validate_attestation_data(state, attestation_data, config)
    else:
        with pytest.raises(ValidationError):
            _validate_attestation_data(state, attestation_data, config)


@pytest.mark.parametrize(
    ("mutator", "is_valid"),
    [
        (lambda c: c, True),
        # crosslink.start_epoch != end_epoch
        (lambda c: c.copy(start_epoch=c.start_epoch + 1), False),
        # end_epoch does not match expected
        (lambda c: c.copy(end_epoch=c.start_epoch + 10), False),
        # parent_root does not match
        (lambda c: c.copy(parent_root=b"\x33" * 32), False),
        # data_root is nonzero
        (lambda c: c.copy(data_root=b"\x33" * 32), False),
    ],
)
def test_validate_crosslink(genesis_state, mutator, is_valid, config):
    some_shard = 3
    parent = genesis_state.current_crosslinks[some_shard]
    target_epoch = config.GENESIS_EPOCH + 1
    valid_crosslink = Crosslink(
        shard=some_shard,
        parent_root=parent.hash_tree_root,
        start_epoch=parent.end_epoch,
        end_epoch=target_epoch,
        data_root=ZERO_HASH32,
    )

    candidate_crosslink = mutator(valid_crosslink)

    if is_valid:
        _validate_crosslink(
            candidate_crosslink, target_epoch, parent, config.MAX_EPOCHS_PER_CROSSLINK
        )
    else:
        with pytest.raises(ValidationError):
            _validate_crosslink(
                candidate_crosslink,
                target_epoch,
                parent,
                config.MAX_EPOCHS_PER_CROSSLINK,
            )
