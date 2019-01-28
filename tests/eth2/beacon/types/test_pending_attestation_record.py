import rlp

from eth2.beacon.types.pending_attestation_records import (
    PendingAttestationRecord,
)


def test_defaults(sample_pending_attestation_record_params):
    pending_attestation = PendingAttestationRecord(**sample_pending_attestation_record_params)

    assert pending_attestation.data == sample_pending_attestation_record_params['data']
    assert pending_attestation.aggregation_bitfield == sample_pending_attestation_record_params['aggregation_bitfield']  # noqa: E501
    assert pending_attestation.custody_bitfield == sample_pending_attestation_record_params['custody_bitfield']  # noqa: E501
    assert pending_attestation.slot_included == sample_pending_attestation_record_params['slot_included']  # noqa: E501
    assert rlp.encode(pending_attestation)
