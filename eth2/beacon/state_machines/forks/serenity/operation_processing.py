from eth_utils import ValidationError

from eth2.beacon.configs import (
    BeaconConfig,
    CommitteeConfig,
)
from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.types.pending_attestation_records import PendingAttestationRecord
from eth2.beacon.types.states import BeaconState
from eth2.beacon.validator_status_helpers import (
    slash_validator,
)

from .block_validation import (
    validate_attestation,
    validate_proposer_slashing,
)


def process_proposer_slashings(state: BeaconState,
                               block: BaseBeaconBlock,
                               config: BeaconConfig) -> BeaconState:
    if len(block.body.proposer_slashings) > config.MAX_PROPOSER_SLASHINGS:
        raise ValidationError(
            f"The block ({block}) has too many proposer slashings:\n"
            f"\tFound {len(block.body.proposer_slashings)} proposer slashings, "
            f"maximum: {config.MAX_PROPOSER_SLASHINGS}"
        )

    for proposer_slashing in block.body.proposer_slashings:
        validate_proposer_slashing(state, proposer_slashing, config.EPOCH_LENGTH)

        state = slash_validator(
            state=state,
            index=proposer_slashing.proposer_index,
            latest_penalized_exit_length=config.LATEST_PENALIZED_EXIT_LENGTH,
            whistleblower_reward_quotient=config.WHISTLEBLOWER_REWARD_QUOTIENT,
            max_deposit_amount=config.MAX_DEPOSIT_AMOUNT,
            committee_config=CommitteeConfig(config),
        )

    return state


def process_attestations(state: BeaconState,
                         block: BaseBeaconBlock,
                         config: BeaconConfig) -> BeaconState:
    """
    Implements 'per-block-processing.operations.attestations' portion of Phase 0 spec:
    https://github.com/ethereum/eth2.0-specs/blob/master/specs/core/0_beacon-chain.md#attestations-1

    Validate the ``attestations`` contained within the ``block`` in the context of ``state``.
    If any invalid, throw ``ValidationError``.
    Otherwise, append an ``PendingAttestationRecords`` for each to ``latest_attestations``.
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
            config.LATEST_BLOCK_ROOTS_LENGTH,
            CommitteeConfig(config),
        )

    # update_latest_attestations
    additional_pending_attestations = tuple(
        PendingAttestationRecord(
            data=attestation.data,
            aggregation_bitfield=attestation.aggregation_bitfield,
            custody_bitfield=attestation.custody_bitfield,
            slot_included=state.slot,
        )
        for attestation in block.body.attestations
    )
    state = state.copy(
        latest_attestations=state.latest_attestations + additional_pending_attestations,
    )
    return state
