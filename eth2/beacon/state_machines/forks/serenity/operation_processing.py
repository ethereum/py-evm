from eth2.beacon.configs import (
    BeaconConfig,
    CommitteeConfig,
)
from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.types.pending_attestation_records import PendingAttestationRecord
from eth2.beacon.types.states import BeaconState

from .block_validation import (
    validate_attestation,
)


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
