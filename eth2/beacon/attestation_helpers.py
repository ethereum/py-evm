from eth2.beacon.committee_helpers import (
    get_epoch_committee_count,
    get_epoch_start_shard,
)
from eth2.beacon.epoch_processing_helpers import (
    get_attesting_indices,
    get_epoch_start_slot,
)
from eth2.beacon.types.attestations import Attestation, IndexedAttestation
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import (
    Slot,
)
from eth2.configs import Eth2Config


def get_attestation_data_slot(state: BeaconState,
                              data: AttestationData,
                              config: Eth2Config) -> Slot:
    committee_count = get_epoch_committee_count(state, data.target_epoch)
    offset = (
        data.crosslink.shard + config.SHARD_COUNT - get_epoch_start_shard(state, data.target_epoch)
    ) % config.SHARD_COUNT
    committees_per_slot = committee_count // config.SLOTS_PER_EPOCH
    return get_epoch_start_slot(data.target_epoch) + offset // committees_per_slot


def convert_to_indexed(state: BeaconState, attestation: Attestation) -> IndexedAttestation:
    attesting_indices = get_attesting_indices(
        state,
        attestation.data,
        attestation.aggregation_bitfield,
    )
    custody_bit_1_indices = get_attesting_indices(
        state,
        attestation.data,
        attestation.custody_bitfield,
    )
    custody_bit_0_indices = tuple(
        index for index in attesting_indices
        if index not in custody_bit_1_indices
    )

    return IndexedAttestation(
        custody_bit_0_indices=custody_bit_0_indices,
        custody_bit_1_indices=custody_bit_1_indices,
        data=attestation.data,
        signature=attestation.signature,
    )


def is_slashable_attestation_data(data_1: AttestationData, data_2: AttestationData) -> bool:
    """
    Check if ``data_1`` and ``data_2`` are slashable according to Casper FFG rules.
    """
    return (
        # Double vote
        (data_1 != data_2 and data_1.target_epoch == data_2.target_epoch) or
        # Surround vote
        (data_1.source_epoch < data_2.source_epoch and data_2.target_epoch < data_1.target_epoch)
    )
