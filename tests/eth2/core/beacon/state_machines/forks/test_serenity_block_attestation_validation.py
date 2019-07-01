import pytest

from eth_utils import (
    ValidationError,
)

from eth.constants import (
    ZERO_HASH32,
)
from eth2.beacon.helpers import (
    get_epoch_start_slot,
)
from eth2.beacon.state_machines.forks.serenity.block_validation import (
    validate_attestation_slot,
    _validate_attestation_data,
    _validate_crosslink,
)
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.crosslinks import Crosslink


@pytest.mark.parametrize(
    ('slots_per_epoch', 'min_attestation_inclusion_delay'),
    [
        (4, 2),
    ]
)
@pytest.mark.parametrize(
    (
        'attestation_slot,'
        'state_slot,'
        'is_valid,'
    ),
    [
        # in bounds at lower end
        (8, 2 + 8, True),
        # in bounds at high end
        (8, 8 + 4, True),
        # state_slot > attestation_slot + slots_per_epoch
        (8, 8 + 4 + 1, False),
        # attestation_slot + min_attestation_inclusion_delay > state_slot
        (8, 8 - 2, False),
    ]
)
def test_validate_attestation_slot(attestation_slot,
                                   state_slot,
                                   slots_per_epoch,
                                   min_attestation_inclusion_delay,
                                   is_valid):

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
        'current_epoch',
        'previous_justified_epoch',
        'current_justified_epoch',
        'previous_justified_root',
        'current_justified_root',
        'slots_per_epoch',
    ),
    [
        (3, 1, 2, b'\x11' * 32, b'\x22' * 32, 8)
    ]
)
@pytest.mark.parametrize(
    (
        'attestation_slot',
        'attestation_source_epoch',
        'attestation_target_epoch',
        'attestation_source_root',
        'is_valid',
    ),
    [
        # slot_to_epoch(attestation_data.slot, slots_per_epoch) >= current_epoch
        # attestation_data.source_epoch == state.current_justified_epoch
        (24, 2, 3, b'\x22' * 32, True),
        # attestation_data.source_epoch != state.current_justified_epoch
        (24, 3, 3, b'\x22' * 32, False),
        # attestation_data.source_root != state.current_justified_root
        (24, 2, 3, b'\x33' * 32, False),
        # slot_to_epoch(attestation_data.slot, slots_per_epoch) < current_epoch
        # attestation_data.source_epoch == state.previous_justified_epoch
        (23, 1, 2, b'\x11' * 32, True),
        # attestation_data.source_epoch != state.previous_justified_epoch
        (23, 2, 2, b'\x11' * 32, False),
        # attestation_data.source_root != state.current_justified_root
        (23, 1, 2, b'\x33' * 32, False),
    ]
)
def test_validate_attestation_source_epoch_and_root(
        genesis_state,
        sample_attestation_data_params,
        attestation_slot,
        attestation_source_epoch,
        attestation_target_epoch,
        attestation_source_root,
        current_epoch,
        previous_justified_epoch,
        current_justified_epoch,
        previous_justified_root,
        current_justified_root,
        slots_per_epoch,
        config,
        mocker,
        is_valid):
    state = genesis_state.copy(
        slot=get_epoch_start_slot(current_epoch, slots_per_epoch) + 5,
        previous_justified_epoch=previous_justified_epoch,
        current_justified_epoch=current_justified_epoch,
        previous_justified_root=previous_justified_root,
        current_justified_root=current_justified_root,
    )
    attestation_data = AttestationData(**sample_attestation_data_params).copy(
        source_epoch=attestation_source_epoch,
        source_root=attestation_source_root,
        target_epoch=attestation_target_epoch,
    )

    mocker.patch(
        'eth2.beacon.state_machines.forks.serenity.block_validation.get_attestation_data_slot',
        return_value=attestation_slot,
    )
    mocker.patch(
        'eth2.beacon.state_machines.forks.serenity.block_validation._validate_crosslink',
    )

    if is_valid:
        _validate_attestation_data(
            state,
            attestation_data,
            config,
        )
    else:
        with pytest.raises(ValidationError):
            _validate_attestation_data(
                state,
                attestation_data,
                config,
            )


@pytest.mark.parametrize(
    (
        'mutator',
        'is_valid',
    ),
    [
        (lambda c: c, True),
        # crosslink.start_epoch != end_epoch
        (lambda c: c.copy(
            start_epoch=c.start_epoch + 1,
        ), False),
        # end_epoch does not match expected
        (lambda c: c.copy(
            end_epoch=c.start_epoch + 10,
        ), False),
        # parent_root does not match
        (lambda c: c.copy(
            parent_root=b'\x33' * 32,
        ), False),
        # data_root is nonzero
        (lambda c: c.copy(
            data_root=b'\x33' * 32,
        ), False),
    ]
)
def test_validate_crosslink(genesis_state,
                            mutator,
                            is_valid,
                            config):
    some_shard = 3
    parent = genesis_state.current_crosslinks[some_shard]
    target_epoch = config.GENESIS_EPOCH + 1
    valid_crosslink = Crosslink(
        shard=some_shard,
        parent_root=parent.root,
        start_epoch=parent.end_epoch,
        end_epoch=target_epoch,
        data_root=ZERO_HASH32,
    )

    candidate_crosslink = mutator(valid_crosslink)

    if is_valid:
        _validate_crosslink(
            candidate_crosslink,
            target_epoch,
            parent,
            config.MAX_EPOCHS_PER_CROSSLINK,
        )
    else:
        with pytest.raises(ValidationError):
            _validate_crosslink(
                candidate_crosslink,
                target_epoch,
                parent,
                config.MAX_EPOCHS_PER_CROSSLINK,
            )
