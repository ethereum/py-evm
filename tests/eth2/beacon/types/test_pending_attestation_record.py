import ssz

from eth2.beacon.types.pending_attestations import (
    PendingAttestation,
)


def test_defaults(sample_pending_attestation_record_params):
    pending_attestation = PendingAttestation(**sample_pending_attestation_record_params)

    assert pending_attestation.data == sample_pending_attestation_record_params['data']
    assert pending_attestation.aggregation_bitfield == sample_pending_attestation_record_params['aggregation_bitfield']  # noqa: E501
    assert pending_attestation.custody_bitfield == sample_pending_attestation_record_params['custody_bitfield']  # noqa: E501
    assert pending_attestation.inclusion_slot == sample_pending_attestation_record_params['inclusion_slot']  # noqa: E501
    assert ssz.encode(pending_attestation)
