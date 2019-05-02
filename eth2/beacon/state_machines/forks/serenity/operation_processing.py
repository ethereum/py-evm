from typing import (
    Iterable,
)
from eth_utils import (
    to_tuple,
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
from eth2.beacon.typing import (
    ValidatorIndex,
)
from eth2.beacon.committee_helpers import (
    slot_to_epoch,
)
from eth2.beacon.types.attester_slashings import AttesterSlashing
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
    validate_slashable_indices,
    validate_voluntary_exit,
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
            state=state,
            index=proposer_slashing.proposer_index,
            latest_slashed_exit_length=config.LATEST_SLASHED_EXIT_LENGTH,
            whistleblower_reward_quotient=config.WHISTLEBLOWER_REWARD_QUOTIENT,
            max_deposit_amount=config.MAX_DEPOSIT_AMOUNT,
            committee_config=CommitteeConfig(config),
        )

    return state


@to_tuple
def _get_slashable_indices(state: BeaconState,
                           config: Eth2Config,
                           attester_slashing: AttesterSlashing) -> Iterable[ValidatorIndex]:
    for index in attester_slashing.slashable_attestation_1.validator_indices:
        should_be_slashed = (
            index in attester_slashing.slashable_attestation_2.validator_indices and
            not state.validator_registry[index].slashed
        )
        if should_be_slashed:
            yield index


def process_attester_slashings(state: BeaconState,
                               block: BaseBeaconBlock,
                               config: Eth2Config) -> BeaconState:
    if len(block.body.attester_slashings) > config.MAX_ATTESTER_SLASHINGS:
        raise ValidationError(
            f"The block ({block}) has too many attester slashings:\n"
            f"\tFound {len(block.body.attester_slashings)} attester slashings, "
            f"maximum: {config.MAX_ATTESTER_SLASHINGS}"
        )

    for attester_slashing in block.body.attester_slashings:
        validate_attester_slashing(
            state,
            attester_slashing,
            config.MAX_INDICES_PER_SLASHABLE_VOTE,
            config.SLOTS_PER_EPOCH,
        )

        slashable_indices = _get_slashable_indices(state, config, attester_slashing)

        validate_slashable_indices(slashable_indices)
        for index in slashable_indices:
            state = slash_validator(
                state=state,
                index=index,
                latest_slashed_exit_length=config.LATEST_SLASHED_EXIT_LENGTH,
                whistleblower_reward_quotient=config.WHISTLEBLOWER_REWARD_QUOTIENT,
                max_deposit_amount=config.MAX_DEPOSIT_AMOUNT,
                committee_config=CommitteeConfig(config),
            )

    return state


def process_attestations(state: BeaconState,
                         block: BaseBeaconBlock,
                         config: Eth2Config) -> BeaconState:
    """
    Implements 'per-block-processing.operations.attestations' portion of Phase 0 spec:
    https://github.com/ethereum/eth2.0-specs/blob/master/specs/core/0_beacon-chain.md#attestations-1

    Validate the ``attestations`` contained within the ``block`` in the context of ``state``.
    If any invalid, throw ``ValidationError``.
    Otherwise, append a ``PendingAttestation`` for each to ``previous_epoch_attestations``
    or ``current_epoch_attestations``.
    Return resulting ``state``.
    """
    if len(block.body.attestations) > config.MAX_ATTESTATIONS:
        raise ValidationError(
            f"The block ({block}) has too many attestations:\n"
            f"\tFound {len(block.body.attestations)} attestations, "
            f"maximum: {config.MAX_ATTESTATIONS}"
        )

    for attestation in block.body.attestations:
        validate_attestation(
            state,
            attestation,
            config.MIN_ATTESTATION_INCLUSION_DELAY,
            config.SLOTS_PER_HISTORICAL_ROOT,
            CommitteeConfig(config),
        )

    # update attestations
    previous_epoch = state.previous_epoch(config.SLOTS_PER_EPOCH)
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    new_previous_epoch_pending_attestations = []
    new_current_epoch_pending_attestations = []
    for attestation in block.body.attestations:
        if slot_to_epoch(attestation.data.slot, config.SLOTS_PER_EPOCH) == current_epoch:
            new_current_epoch_pending_attestations.append(
                PendingAttestation(
                    aggregation_bitfield=attestation.aggregation_bitfield,
                    data=attestation.data,
                    custody_bitfield=attestation.custody_bitfield,
                    inclusion_slot=state.slot,
                )
            )
        elif slot_to_epoch(attestation.data.slot, config.SLOTS_PER_EPOCH) == previous_epoch:
            new_previous_epoch_pending_attestations.append(
                PendingAttestation(
                    aggregation_bitfield=attestation.aggregation_bitfield,
                    data=attestation.data,
                    custody_bitfield=attestation.custody_bitfield,
                    inclusion_slot=state.slot,
                )
            )

    state = state.copy(
        previous_epoch_attestations=(
            state.previous_epoch_attestations + tuple(new_previous_epoch_pending_attestations)
        ),
        current_epoch_attestations=(
            state.current_epoch_attestations + tuple(new_current_epoch_pending_attestations)
        ),
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
        # Run the exit
        state = initiate_validator_exit(state, voluntary_exit.validator_index)

    return state


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
            slots_per_epoch=config.SLOTS_PER_EPOCH,
            deposit_contract_tree_depth=config.DEPOSIT_CONTRACT_TREE_DEPTH,
        )

    return state
