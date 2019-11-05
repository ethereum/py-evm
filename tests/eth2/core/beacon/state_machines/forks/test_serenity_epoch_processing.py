import pytest

from eth2._utils.bitfield import get_empty_bitfield, set_voted
from eth2.beacon.committee_helpers import (
    get_beacon_proposer_index,
    iterate_committees_at_epoch,
)
from eth2.beacon.constants import (
    FAR_FUTURE_EPOCH,
    GWEI_PER_ETH,
    JUSTIFICATION_BITS_LENGTH,
)
from eth2.beacon.helpers import (
    compute_start_slot_at_epoch,
    get_block_root,
    get_block_root_at_slot,
)
from eth2.beacon.state_machines.forks.serenity.epoch_processing import (
    _bft_threshold_met,
    _determine_new_finalized_epoch,
    _determine_slashing_penalty,
    compute_activation_exit_epoch,
    get_attestation_deltas,
    process_justification_and_finalization,
    process_registry_updates,
    process_slashings,
)
from eth2.beacon.tools.builder.validator import (
    mk_all_pending_attestations_with_full_participation_in_epoch,
)
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.checkpoints import Checkpoint
from eth2.beacon.types.pending_attestations import PendingAttestation
from eth2.beacon.types.validators import Validator
from eth2.beacon.typing import Gwei
from eth2.configs import CommitteeConfig


@pytest.mark.parametrize(
    "total_balance," "attesting_balance," "expected,",
    (
        (1500 * GWEI_PER_ETH, 1000 * GWEI_PER_ETH, True),
        (1500 * GWEI_PER_ETH, 999 * GWEI_PER_ETH, False),
    ),
)
def test_bft_threshold_met(attesting_balance, total_balance, expected):
    assert _bft_threshold_met(attesting_balance, total_balance) == expected


@pytest.mark.parametrize(
    "justification_bits,"
    "previous_justified_epoch,"
    "current_justified_epoch,"
    "expected,",
    (
        # Rule 1
        ((False, True, True, True), 3, 3, 3),
        # Rule 2
        ((False, True, True, False), 4, 4, 4),
        # Rule 3
        ((True, True, True, False), 3, 4, 4),
        # Rule 4
        ((True, True, False, False), 2, 5, 5),
        # No finalize
        ((False, False, False, False), 2, 2, 1),
        ((True, True, True, True), 2, 2, 1),
    ),
)
def test_get_finalized_epoch(
    justification_bits, previous_justified_epoch, current_justified_epoch, expected
):
    current_epoch = 6
    finalized_epoch = 1
    assert (
        _determine_new_finalized_epoch(
            finalized_epoch,
            previous_justified_epoch,
            current_justified_epoch,
            current_epoch,
            justification_bits,
        )
        == expected
    )


def test_justification_without_mock(genesis_state, slots_per_historical_root, config):

    state = genesis_state
    state = process_justification_and_finalization(state, config)
    assert state.justification_bits == (False,) * JUSTIFICATION_BITS_LENGTH


def _convert_to_bitfield(bits):
    data = bits.to_bytes(1, "little")
    length = bits.bit_length()
    bitfield = get_empty_bitfield(length)
    for index in range(length):
        value = (data[index // 8] >> index % 8) % 2
        if value:
            bitfield = set_voted(bitfield, index)
    return (bitfield + (False,) * (4 - length))[0:4]


@pytest.mark.parametrize(
    (
        "current_epoch",
        "current_epoch_justifiable",
        "previous_epoch_justifiable",
        "previous_justified_epoch",
        "current_justified_epoch",
        "justification_bits",
        "finalized_epoch",
        "justified_epoch_after",
        "justification_bits_after",
        "finalized_epoch_after",
    ),
    (
        # No processing on first and second epochs
        (0, True, False, 0, 0, 0b0, 0, 0, 0b0, 0),
        (1, True, True, 0, 0, 0b1, 0, 0, 0b1, 0),
        # Trigger R4 to finalize epoch 1
        (2, True, True, 0, 1, 0b11, 0, 2, 0b111, 1),  # R4 finalize 1
        # Trigger R2 to finalize epoch 1
        # Trigger R3 to finalize epoch 2
        (2, False, True, 0, 1, 0b11, 0, 1, 0b110, 0),  # R2 finalize 0
        (3, False, True, 1, 1, 0b110, 0, 2, 0b1110, 1),  # R2 finalize 1
        (4, True, True, 1, 2, 0b1110, 1, 4, 0b11111, 2),  # R3 finalize 2
        # Trigger R1 to finalize epoch 2
        (2, False, True, 0, 1, 0b11, 0, 1, 0b110, 0),  # R2 finalize 0
        (3, False, True, 1, 1, 0b110, 0, 2, 0b1110, 1),  # R2 finalize 1
        (4, False, True, 1, 2, 0b1110, 1, 3, 0b11110, 1),  # R1 finalize 1
        (5, False, True, 2, 3, 0b11110, 1, 4, 0b111110, 2),  # R1 finalize 2
    ),
)
def test_process_justification_and_finalization(
    genesis_state,
    current_epoch,
    current_epoch_justifiable,
    previous_epoch_justifiable,
    previous_justified_epoch,
    current_justified_epoch,
    justification_bits,
    finalized_epoch,
    justified_epoch_after,
    justification_bits_after,
    finalized_epoch_after,
    config,
):
    justification_bits = _convert_to_bitfield(justification_bits)
    justification_bits_after = _convert_to_bitfield(justification_bits_after)
    previous_epoch = max(current_epoch - 1, 0)
    slot = (current_epoch + 1) * config.SLOTS_PER_EPOCH - 1

    state = genesis_state.copy(
        slot=slot,
        previous_justified_checkpoint=Checkpoint(epoch=previous_justified_epoch),
        current_justified_checkpoint=Checkpoint(epoch=current_justified_epoch),
        justification_bits=justification_bits,
        finalized_checkpoint=Checkpoint(epoch=finalized_epoch),
        block_roots=tuple(
            i.to_bytes(32, "little") for i in range(config.SLOTS_PER_HISTORICAL_ROOT)
        ),
    )

    if previous_epoch_justifiable:
        attestations = mk_all_pending_attestations_with_full_participation_in_epoch(
            state, previous_epoch, config
        )
        state = state.copy(previous_epoch_attestations=attestations)

    if current_epoch_justifiable:
        attestations = mk_all_pending_attestations_with_full_participation_in_epoch(
            state, current_epoch, config
        )
        state = state.copy(current_epoch_attestations=attestations)

    post_state = process_justification_and_finalization(state, config)

    assert (
        post_state.previous_justified_checkpoint.epoch
        == state.current_justified_checkpoint.epoch
    )
    assert post_state.current_justified_checkpoint.epoch == justified_epoch_after
    assert post_state.justification_bits == justification_bits_after
    assert post_state.finalized_checkpoint.epoch == finalized_epoch_after


# TODO better testing on attestation deltas
@pytest.mark.parametrize(
    (
        "validator_count",
        "slots_per_epoch",
        "min_epochs_to_inactivity_penalty",
        "target_committee_size",
    ),
    [(100, 8, 4, 10)],
)
@pytest.mark.parametrize(
    ("finalized_epoch", "current_slot"),
    [
        (
            4,
            (4 + 1 + 4) * 8,
        ),  # epochs_since_finality <= min_epochs_to_inactivity_penalty
        (
            4,
            (4 + 1 + 5) * 8,
        ),  # epochs_since_finality > min_epochs_to_inactivity_penalty
    ],
)
def test_get_attestation_deltas(
    genesis_state,
    config,
    slots_per_epoch,
    target_committee_size,
    max_committees_per_slot,
    min_attestation_inclusion_delay,
    inactivity_penalty_quotient,
    finalized_epoch,
    current_slot,
    sample_pending_attestation_record_params,
    sample_attestation_data_params,
):

    state = genesis_state.copy(
        slot=current_slot, finalized_checkpoint=Checkpoint(epoch=finalized_epoch)
    )
    previous_epoch = state.previous_epoch(config.SLOTS_PER_EPOCH, config.GENESIS_EPOCH)
    has_inactivity_penalty = (
        previous_epoch - finalized_epoch > config.MIN_EPOCHS_TO_INACTIVITY_PENALTY
    )

    indices_to_check = set()

    prev_epoch_attestations = tuple()

    for committee, committee_index, slot in iterate_committees_at_epoch(
        state, previous_epoch, config
    ):
        participants_bitfield = get_empty_bitfield(len(committee))
        for i, index in enumerate(committee):
            indices_to_check.add(index)
            participants_bitfield = set_voted(participants_bitfield, i)
        prev_epoch_attestations += (
            PendingAttestation(**sample_pending_attestation_record_params).copy(
                aggregation_bits=participants_bitfield,
                inclusion_delay=min_attestation_inclusion_delay,
                proposer_index=get_beacon_proposer_index(
                    state.copy(slot=slot), CommitteeConfig(config)
                ),
                data=AttestationData(**sample_attestation_data_params).copy(
                    slot=slot,
                    index=committee_index,
                    beacon_block_root=get_block_root_at_slot(
                        state, slot, config.SLOTS_PER_HISTORICAL_ROOT
                    ),
                    target=Checkpoint(
                        epoch=previous_epoch,
                        root=get_block_root(
                            state,
                            previous_epoch,
                            config.SLOTS_PER_EPOCH,
                            config.SLOTS_PER_HISTORICAL_ROOT,
                        ),
                    ),
                ),
            ),
        )
    state = state.copy(previous_epoch_attestations=prev_epoch_attestations)

    rewards_received, penalties_received = get_attestation_deltas(state, config)
    if has_inactivity_penalty:
        assert sum(penalties_received) > 0
    else:
        assert sum(penalties_received) == 0
    assert all(reward > 0 for reward in rewards_received)


@pytest.mark.parametrize(
    (
        "validator_count",
        "slots_per_epoch",
        "target_committee_size",
        "max_committees_per_slot",
    ),
    [(10, 10, 9, 10)],
)
def test_process_registry_updates(
    validator_count, genesis_state, config, slots_per_epoch
):
    activation_index = len(genesis_state.validators)
    exiting_index = len(genesis_state.validators) - 1

    activating_validator = Validator.create_pending_validator(
        pubkey=b"\x10" * 48,
        withdrawal_credentials=b"\x11" * 32,
        amount=Gwei(32 * GWEI_PER_ETH),
        config=config,
    )

    state = genesis_state.copy(
        validators=genesis_state.validators[:exiting_index]
        + (
            genesis_state.validators[exiting_index].copy(
                effective_balance=config.EJECTION_BALANCE - 1
            ),
        )
        + (activating_validator,),
        balances=genesis_state.balances + (config.MAX_EFFECTIVE_BALANCE,),
    )

    # handles activations
    post_state = process_registry_updates(state, config)

    # Check if the activating_validator is activated
    pre_activation_validator = state.validators[activation_index]
    post_activation_validator = post_state.validators[activation_index]
    assert pre_activation_validator.activation_eligibility_epoch == FAR_FUTURE_EPOCH
    assert pre_activation_validator.activation_epoch == FAR_FUTURE_EPOCH
    assert post_activation_validator.activation_eligibility_epoch != FAR_FUTURE_EPOCH
    activation_epoch = compute_activation_exit_epoch(
        state.current_epoch(config.SLOTS_PER_EPOCH), config.MAX_SEED_LOOKAHEAD
    )
    assert post_activation_validator.is_active(activation_epoch)
    # Check if the activating_validator is exited
    pre_exiting_validator = state.validators[exiting_index]
    post_exiting_validator = post_state.validators[exiting_index]
    assert pre_exiting_validator.exit_epoch == FAR_FUTURE_EPOCH
    assert pre_exiting_validator.withdrawable_epoch == FAR_FUTURE_EPOCH
    assert state.validators[exiting_index].effective_balance <= config.EJECTION_BALANCE
    assert post_exiting_validator.exit_epoch != FAR_FUTURE_EPOCH
    assert post_exiting_validator.withdrawable_epoch != FAR_FUTURE_EPOCH
    assert post_exiting_validator.withdrawable_epoch > post_exiting_validator.exit_epoch


@pytest.mark.parametrize(
    (
        "validator_count",
        "slots_per_epoch",
        "genesis_slot",
        "current_epoch",
        "epochs_per_slashings_vector",
    ),
    [(10, 4, 8, 8, 8)],
)
@pytest.mark.parametrize(
    ("total_penalties", "total_balance", "expected_penalty"),
    [
        # total_penalties * 3 is less than total_balance
        (
            32 * 10 ** 9,  # 1 ETH
            (32 * 10 ** 9 * 10),
            # effective_balance * total_penalties * 3 // total_balance
            ((32 * 10 ** 9) // 10 ** 9)
            * (3 * 32 * 10 ** 9)
            // (32 * 10 ** 9 * 10)
            * 10 ** 9,
        ),
        # total_balance is less than total_penalties * 3
        (
            32 * 4 * 10 ** 9,
            (32 * 10 ** 9 * 10),
            # effective_balance * total_balance // total_balance,
            (32 * 10 ** 9)
            // 10 ** 9
            * (32 * 10 ** 9 * 10)
            // (32 * 10 ** 9 * 10)
            * 10 ** 9,
        ),
    ],
)
def test_determine_slashing_penalty(
    genesis_state,
    config,
    slots_per_epoch,
    current_epoch,
    epochs_per_slashings_vector,
    total_penalties,
    total_balance,
    expected_penalty,
):
    state = genesis_state.copy(
        slot=compute_start_slot_at_epoch(current_epoch, slots_per_epoch)
    )
    # if the size of the v-set changes then update the parameters above
    assert len(state.validators) == 10
    validator_index = 0
    penalty = _determine_slashing_penalty(
        total_penalties,
        total_balance,
        state.validators[validator_index].effective_balance,
        config.EFFECTIVE_BALANCE_INCREMENT,
    )
    assert penalty == expected_penalty


@pytest.mark.parametrize(
    (
        "validator_count",
        "slots_per_epoch",
        "current_epoch",
        "epochs_per_slashings_vector",
        "slashings",
        "expected_penalty",
    ),
    [
        (
            10,
            4,
            8,
            8,
            (19 * 10 ** 9, 10 ** 9) + (0,) * 6,
            (32 * 10 ** 9 // 10 ** 9 * 60 * 10 ** 9) // (320 * 10 ** 9) * 10 ** 9,
        )
    ],
)
def test_process_slashings(
    genesis_state,
    config,
    current_epoch,
    slashings,
    slots_per_epoch,
    epochs_per_slashings_vector,
    expected_penalty,
):
    state = genesis_state.copy(
        slot=compute_start_slot_at_epoch(current_epoch, slots_per_epoch),
        slashings=slashings,
    )
    slashing_validator_index = 0
    validator = state.validators[slashing_validator_index].copy(
        slashed=True,
        withdrawable_epoch=current_epoch + epochs_per_slashings_vector // 2,
    )
    state = state.update_validator(slashing_validator_index, validator)

    result_state = process_slashings(state, config)
    penalty = (
        state.balances[slashing_validator_index]
        - result_state.balances[slashing_validator_index]
    )
    assert penalty == expected_penalty
