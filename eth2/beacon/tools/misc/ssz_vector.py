from typing import Dict

import ssz
import ssz.sedes as sedes

from eth2.beacon.types.attestations import Attestation, IndexedAttestation
from eth2.beacon.types.blocks import BeaconBlockBody
from eth2.beacon.types.compact_committees import CompactCommittee
from eth2.beacon.types.historical_batch import HistoricalBatch
from eth2.beacon.types.pending_attestations import PendingAttestation
from eth2.beacon.types.states import BeaconState
from eth2.configs import Eth2Config


def _mk_overrides(config: Eth2Config) -> Dict[ssz.Serializable, Dict[str, int]]:
    return {
        Attestation: {
            "aggregation_bits": config.MAX_VALIDATORS_PER_COMMITTEE,
            "custody_bits": config.MAX_VALIDATORS_PER_COMMITTEE,
        },
        BeaconBlockBody: {
            "proposer_slashings": config.MAX_PROPOSER_SLASHINGS,
            "attester_slashings": config.MAX_ATTESTER_SLASHINGS,
            "attestations": config.MAX_ATTESTATIONS,
            "deposits": config.MAX_DEPOSITS,
            "voluntary_exits": config.MAX_VOLUNTARY_EXITS,
            "transfers": config.MAX_TRANSFERS,
        },
        BeaconState: {
            "block_roots": config.SLOTS_PER_HISTORICAL_ROOT,
            "state_roots": config.SLOTS_PER_HISTORICAL_ROOT,
            "historical_roots": config.HISTORICAL_ROOTS_LIMIT,
            "eth1_data_votes": config.SLOTS_PER_ETH1_VOTING_PERIOD,
            "validators": config.VALIDATOR_REGISTRY_LIMIT,
            "balances": config.VALIDATOR_REGISTRY_LIMIT,
            "randao_mixes": config.EPOCHS_PER_HISTORICAL_VECTOR,
            "active_index_roots": config.EPOCHS_PER_HISTORICAL_VECTOR,
            "compact_committees_roots": config.EPOCHS_PER_HISTORICAL_VECTOR,
            "slashings": config.EPOCHS_PER_SLASHINGS_VECTOR,
            "previous_epoch_attestations": config.MAX_ATTESTATIONS
            * config.SLOTS_PER_EPOCH,
            "current_epoch_attestations": config.MAX_ATTESTATIONS
            * config.SLOTS_PER_EPOCH,
            "previous_crosslinks": config.SHARD_COUNT,
            "current_crosslinks": config.SHARD_COUNT,
        },
        CompactCommittee: {
            "pubkeys": config.MAX_VALIDATORS_PER_COMMITTEE,
            "compact_validators": config.MAX_VALIDATORS_PER_COMMITTEE,
        },
        HistoricalBatch: {
            "block_roots": config.SLOTS_PER_HISTORICAL_ROOT,
            "state_roots": config.SLOTS_PER_HISTORICAL_ROOT,
        },
        IndexedAttestation: {
            "custody_bit_0_indices": config.MAX_VALIDATORS_PER_COMMITTEE,
            "custody_bit_1_indices": config.MAX_VALIDATORS_PER_COMMITTEE,
        },
        PendingAttestation: {"aggregation_bits": config.MAX_VALIDATORS_PER_COMMITTEE},
    }


def override_lengths(config: Eth2Config) -> None:
    all_overrides = _mk_overrides(config)

    for typ, overrides in all_overrides.items():
        for index, field_sedes in enumerate(typ._meta.container_sedes.field_sedes):
            field_name = typ._meta.fields[index][0]
            if field_name in overrides:
                if isinstance(field_sedes, sedes.Bitlist):
                    field_sedes.max_bit_count = overrides[field_name]
                if isinstance(field_sedes, sedes.List):
                    field_sedes.max_length = overrides[field_name]
                if isinstance(field_sedes, sedes.Vector):
                    field_sedes.length = overrides[field_name]
