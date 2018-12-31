from eth.beacon.types.blocks import BaseBeaconBlock
from eth.beacon.types.pending_attestation_records import PendingAttestationRecord
from eth.beacon.types.states import BeaconState
from eth.beacon.state_machines.configs import BeaconConfig
from eth.beacon.helpers import get_beacon_proposer_index
from eth._utils.numeric import bitwise_xor

from .validation import (
    validate_serenity_attestation,
    validate_serenity_randao_reveal,
)


def validate_randao(state: BeaconState,
                    block: BaseBeaconBlock,
                    config: BeaconConfig) -> BeaconState:
    """
    Implements 'per-block-processing.RANDAO' portion of Phase 0 spec:
    https://github.com/ethereum/eth2.0-specs/blob/master/specs/core/0_beacon-chain.md#randao

    Verify the ``randao_reveal`` contained within the ``block`` in the context of
    ``randao_commitment`` in the ``state``

    """
    proposer_index = get_beacon_proposer_index(state, state.slot, config.EPOCH_LENGTH)

    validator_registry = list(state.validator_registry)
    latest_randao_mixes = list(state.latest_randao_mixes)

    proposer = validator_registry[proposer_index]

    validate_serenity_randao_reveal(block, proposer)

    latest_randao_mix = latest_randao_mixes[state.slot % config.LATEST_RANDAO_MIXES_LENGTH]
    latest_randao_mix = bitwise_xor(latest_randao_mix, block.randao_reveal)

    proposer = proposer.copy(
        randao_commitment=block.randao_reveal,
        randao_layers=0,
    )
    latest_randao_mixes[state.slot % config.LATEST_RANDAO_MIXES_LENGTH] = latest_randao_mix

    state = state.copy(
        validator_registry=tuple(validator_registry),
        latest_randao_mixes=tuple(latest_randao_mixes),
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
    for attestation in block.body.attestations:
        validate_serenity_attestation(
            state,
            attestation,
            config.EPOCH_LENGTH,
            config.MIN_ATTESTATION_INCLUSION_DELAY,
        )

    # update_latest_attestations
    additional_pending_attestations = tuple(
        PendingAttestationRecord(
            data=attestation.data,
            participation_bitfield=attestation.participation_bitfield,
            custody_bitfield=attestation.custody_bitfield,
            slot_included=state.slot,
        )
        for attestation in block.body.attestations
    )
    state = state.copy(
        latest_attestations=state.latest_attestations + additional_pending_attestations,
    )
    return state
