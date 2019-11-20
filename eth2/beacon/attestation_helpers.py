from eth_utils import ValidationError

from eth2._utils.bls import bls
from eth2.beacon.exceptions import SignatureError
from eth2.beacon.helpers import get_domain
from eth2.beacon.signature_domain import SignatureDomain
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.attestations import IndexedAttestation
from eth2.beacon.types.states import BeaconState


def validate_indexed_attestation_aggregate_signature(
    state: BeaconState, indexed_attestation: IndexedAttestation, slots_per_epoch: int
) -> None:
    attesting_indices = indexed_attestation.attesting_indices
    pubkey = bls.aggregate_pubkeys(
        tuple(state.validators[i].pubkey for i in attesting_indices)
    )

    message_hash = indexed_attestation.data.hash_tree_root
    domain = get_domain(
        state,
        SignatureDomain.DOMAIN_BEACON_ATTESTER,
        slots_per_epoch,
        indexed_attestation.data.target.epoch,
    )
    bls.validate(
        pubkey=pubkey,
        message_hash=message_hash,
        signature=indexed_attestation.signature,
        domain=domain,
    )


def validate_indexed_attestation(
    state: BeaconState,
    indexed_attestation: IndexedAttestation,
    max_validators_per_committee: int,
    slots_per_epoch: int,
    validate_signature: bool = True,
) -> None:
    """
    Derived from spec: `is_valid_indexed_attestation`.

    Option ``validate_signature`` is used in some testing scenarios, like some fork choice tests.
    """
    attesting_indices = indexed_attestation.attesting_indices

    if len(attesting_indices) > max_validators_per_committee:
        raise ValidationError(
            f"Require no more than {max_validators_per_committee} validators per attestation,"
            f" but have {len(attesting_indices)} validators."
        )

    if attesting_indices != tuple(sorted(attesting_indices)):
        raise ValidationError(
            f"Indices should be sorted; the attesting indices are not: {attesting_indices}."
        )

    if validate_signature:
        try:
            validate_indexed_attestation_aggregate_signature(
                state, indexed_attestation, slots_per_epoch
            )
        except SignatureError as error:
            raise ValidationError(
                f"Incorrect aggregate signature on the {indexed_attestation}", error
            )


def is_slashable_attestation_data(
    data_1: AttestationData, data_2: AttestationData
) -> bool:
    """
    Check if ``data_1`` and ``data_2`` are slashable according to Casper FFG rules.
    """
    # NOTE: checking 'double vote' OR 'surround vote'
    return (data_1 != data_2 and data_1.target.epoch == data_2.target.epoch) or (
        data_1.source.epoch < data_2.source.epoch
        and data_2.target.epoch < data_1.target.epoch
    )
