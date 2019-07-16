from eth2._utils.bls import (
    bls,
)

from eth_utils import (
    ValidationError,
)

from eth2.beacon.helpers import (
    get_active_validator_indices,
    get_domain,
    get_epoch_start_slot,
)
from eth2.beacon.committee_helpers import (
    get_epoch_committee_count,
    get_epoch_start_shard,
)
from eth2.beacon.signature_domain import SignatureDomain
from eth2.beacon.types.attestations import IndexedAttestation
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.attestation_data_and_custody_bits import AttestationDataAndCustodyBit
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import (
    Slot,
)
from eth2.configs import (
    CommitteeConfig,
    Eth2Config,
)
from eth2.beacon.exceptions import (
    SignatureError,
)


def get_attestation_data_slot(state: BeaconState,
                              data: AttestationData,
                              config: Eth2Config) -> Slot:
    active_validator_indices = get_active_validator_indices(
        state.validators,
        data.target_epoch,
    )
    committee_count = get_epoch_committee_count(
        len(active_validator_indices),
        config.SHARD_COUNT,
        config.SLOTS_PER_EPOCH,
        config.TARGET_COMMITTEE_SIZE,
    )
    offset = (
        data.crosslink.shard + config.SHARD_COUNT - get_epoch_start_shard(
            state,
            data.target_epoch,
            CommitteeConfig(config),
        )
    ) % config.SHARD_COUNT
    committees_per_slot = committee_count // config.SLOTS_PER_EPOCH
    return get_epoch_start_slot(
        data.target_epoch,
        config.SLOTS_PER_EPOCH,
    ) + offset // committees_per_slot


def validate_indexed_attestation_aggregate_signature(state: BeaconState,
                                                     indexed_attestation: IndexedAttestation,
                                                     slots_per_epoch: int) -> None:
    bit_0_indices = indexed_attestation.custody_bit_0_indices
    bit_1_indices = indexed_attestation.custody_bit_1_indices

    pubkeys = (
        bls.aggregate_pubkeys(
            tuple(state.validators[i].pubkey for i in bit_0_indices)
        ),
        bls.aggregate_pubkeys(
            tuple(state.validators[i].pubkey for i in bit_1_indices)
        ),
    )

    message_hashes = (
        AttestationDataAndCustodyBit(
            data=indexed_attestation.data,
            custody_bit=False
        ).root,
        AttestationDataAndCustodyBit(
            data=indexed_attestation.data,
            custody_bit=True,
        ).root,
    )

    domain = get_domain(
        state,
        SignatureDomain.DOMAIN_ATTESTATION,
        slots_per_epoch,
        indexed_attestation.data.target_epoch,
    )
    bls.validate_multiple(
        pubkeys=pubkeys,
        message_hashes=message_hashes,
        signature=indexed_attestation.signature,
        domain=domain,
    )


def validate_indexed_attestation(state: BeaconState,
                                 indexed_attestation: IndexedAttestation,
                                 max_indices_per_attestation: int,
                                 slots_per_epoch: int) -> None:
    bit_0_indices = indexed_attestation.custody_bit_0_indices
    bit_1_indices = indexed_attestation.custody_bit_1_indices

    if len(bit_1_indices) != 0:
        raise ValidationError(
            f"Expected no custody bit 1 validators (cf. {bit_1_indices})."
        )

    if len(bit_0_indices) + len(bit_1_indices) > max_indices_per_attestation:
        raise ValidationError(
            f"Require no more than {max_indices_per_attestation} validators per attestation,"
            f" but have {len(bit_0_indices)} 0-bit validators"
            f" and {len(bit_1_indices)} 1-bit validators."
        )

    intersection = set(bit_0_indices).intersection(bit_1_indices)
    if len(intersection) != 0:
        raise ValidationError(
            f"Index sets by custody bits must be disjoint but have the following"
            f" indices in common: {intersection}."
        )

    if bit_0_indices != tuple(sorted(bit_0_indices)):
        raise ValidationError(
            f"Indices should be sorted; the 0-bit indices are not: {bit_0_indices}."
        )

    if bit_1_indices != tuple(sorted(bit_1_indices)):
        raise ValidationError(
            f"Indices should be sorted; the 1-bit indices are not: {bit_1_indices}."
        )

    try:
        validate_indexed_attestation_aggregate_signature(state,
                                                         indexed_attestation,
                                                         slots_per_epoch)
    except SignatureError as error:
        raise ValidationError(
            f"Incorrect aggregate signature on the {indexed_attestation}",
            error,
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
