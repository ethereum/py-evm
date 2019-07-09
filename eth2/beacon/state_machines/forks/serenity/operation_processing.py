from typing import (
    Tuple,
)

from eth_utils import (
    ValidationError,
)

from eth2.configs import (
    Eth2Config,
    CommitteeConfig,
)
from eth2.beacon.validator_status_helpers import (
    initiate_validator_exit,
    slash_validator,
)
from eth2.beacon.attestation_helpers import (
    get_attestation_data_slot,
)
from eth2.beacon.committee_helpers import (
    get_beacon_proposer_index,
)
from eth2.beacon.epoch_processing_helpers import (
    increase_balance,
    decrease_balance,
)
from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.types.pending_attestations import PendingAttestation
from eth2.beacon.types.states import BeaconState
from eth2.beacon.deposit_helpers import (
    process_deposit,
)

from .block_validation import (
    validate_attestation,
    validate_attester_slashing,
    validate_proposer_slashing,
    validate_voluntary_exit,
    validate_correct_number_of_deposits,
    validate_some_slashing,
    validate_transfer,
    validate_unique_transfers,
)


def process_proposer_slashings(state: BeaconState,
                               block: BaseBeaconBlock,
                               config: Eth2Config) -> BeaconState:
    if len(block.body.proposer_slashings) > config.MAX_PROPOSER_SLASHINGS:
        raise ValidationError(
            f"The block ({block}) has too many proposer slashings:\n"
            f"\tFound {len(block.body.proposer_slashings)} proposer slashings, "
            f"maximum: {config.MAX_PROPOSER_SLASHINGS}"
        )

    for proposer_slashing in block.body.proposer_slashings:
        validate_proposer_slashing(state, proposer_slashing, config.SLOTS_PER_EPOCH)

        state = slash_validator(
            state,
            proposer_slashing.proposer_index,
            config,
        )

    return state


def process_attester_slashings(state: BeaconState,
                               block: BaseBeaconBlock,
                               config: Eth2Config) -> BeaconState:
    if len(block.body.attester_slashings) > config.MAX_ATTESTER_SLASHINGS:
        raise ValidationError(
            f"The block ({block}) has too many attester slashings:\n"
            f"\tFound {len(block.body.attester_slashings)} attester slashings, "
            f"maximum: {config.MAX_ATTESTER_SLASHINGS}"
        )

    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)

    for attester_slashing in block.body.attester_slashings:
        validate_attester_slashing(
            state,
            attester_slashing,
            config.MAX_INDICES_PER_ATTESTATION,
            config.SLOTS_PER_EPOCH,
        )

        slashed_any = False
        attestation_1 = attester_slashing.attestation_1
        attestation_2 = attester_slashing.attestation_2
        attesting_indices_1 = (
            attestation_1.custody_bit_0_indices + attestation_1.custody_bit_1_indices
        )
        attesting_indices_2 = (
            attestation_2.custody_bit_0_indices + attestation_2.custody_bit_1_indices
        )

        eligible_indices = sorted(set(attesting_indices_1).intersection(attesting_indices_2))
        for index in eligible_indices:
            validator = state.validators[index]
            if validator.is_slashable(current_epoch):
                state = slash_validator(
                    state,
                    index,
                    config,
                )
                slashed_any = True
        validate_some_slashing(slashed_any, attester_slashing)

    return state


def process_attestations(state: BeaconState,
                         block: BaseBeaconBlock,
                         config: Eth2Config) -> BeaconState:
    if len(block.body.attestations) > config.MAX_ATTESTATIONS:
        raise ValidationError(
            f"The block has too many attestations:\n"
            f"\tFound {len(block.body.attestations)} attestations, "
            f"maximum: {config.MAX_ATTESTATIONS}"
        )

    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    new_current_epoch_attestations: Tuple[PendingAttestation, ...] = tuple()
    new_previous_epoch_attestations: Tuple[PendingAttestation, ...] = tuple()
    for attestation in block.body.attestations:
        validate_attestation(
            state,
            attestation,
            config,
        )

        attestation_slot = get_attestation_data_slot(
            state,
            attestation.data,
            config,
        )
        proposer_index = get_beacon_proposer_index(
            state,
            CommitteeConfig(config),
        )
        pending_attestation = PendingAttestation(
            aggregation_bitfield=attestation.aggregation_bitfield,
            data=attestation.data,
            inclusion_delay=state.slot - attestation_slot,
            proposer_index=proposer_index,
        )

        if attestation.data.target_epoch == current_epoch:
            new_current_epoch_attestations += (pending_attestation,)
        else:
            new_previous_epoch_attestations += (pending_attestation,)

    return state.copy(
        current_epoch_attestations=(
            state.current_epoch_attestations + new_current_epoch_attestations
        ),
        previous_epoch_attestations=(
            state.previous_epoch_attestations + new_previous_epoch_attestations
        ),
    )


def process_deposits(state: BeaconState,
                     block: BaseBeaconBlock,
                     config: Eth2Config) -> BeaconState:
    if len(block.body.deposits) > config.MAX_DEPOSITS:
        raise ValidationError(
            f"The block ({block}) has too many deposits:\n"
            f"\tFound {len(block.body.deposits)} deposits, "
            f"maximum: {config.MAX_DEPOSITS}"
        )

    for deposit in block.body.deposits:
        state = process_deposit(
            state,
            deposit,
            config,
        )

    return state


def process_voluntary_exits(state: BeaconState,
                            block: BaseBeaconBlock,
                            config: Eth2Config) -> BeaconState:
    if len(block.body.voluntary_exits) > config.MAX_VOLUNTARY_EXITS:
        raise ValidationError(
            f"The block ({block}) has too many voluntary exits:\n"
            f"\tFound {len(block.body.voluntary_exits)} voluntary exits, "
            f"maximum: {config.MAX_VOLUNTARY_EXITS}"
        )

    for voluntary_exit in block.body.voluntary_exits:
        validate_voluntary_exit(
            state,
            voluntary_exit,
            config.SLOTS_PER_EPOCH,
            config.PERSISTENT_COMMITTEE_PERIOD,
        )
        state = initiate_validator_exit(state, voluntary_exit.validator_index, config)

    return state


def process_transfers(state: BeaconState,
                      block: BaseBeaconBlock,
                      config: Eth2Config) -> BeaconState:
    if len(block.body.transfers) > config.MAX_TRANSFERS:
        raise ValidationError(
            f"The block ({block}) has too many transfers:\n"
            f"\tFound {len(block.body.transfers)} transfers, "
            f"maximum: {config.MAX_TRANSFERS}"
        )

    for transfer in block.body.transfers:
        validate_transfer(
            state,
            transfer,
            config,
        )
        state = decrease_balance(
            state,
            transfer.sender,
            transfer.amount + transfer.fee,
        )
        state = increase_balance(
            state,
            transfer.recipient,
            transfer.amount,
        )
        state = increase_balance(
            state,
            get_beacon_proposer_index(
                state,
                CommitteeConfig(config),
            ),
            transfer.fee,
        )

    return state


def process_operations(state: BeaconState,
                       block: BaseBeaconBlock,
                       config: Eth2Config) -> BeaconState:
    validate_correct_number_of_deposits(state, block, config)
    validate_unique_transfers(state, block, config)

    state = process_proposer_slashings(state, block, config)
    state = process_attester_slashings(state, block, config)
    state = process_attestations(state, block, config)
    state = process_deposits(state, block, config)
    state = process_voluntary_exits(state, block, config)
    state = process_transfers(state, block, config)

    return state
