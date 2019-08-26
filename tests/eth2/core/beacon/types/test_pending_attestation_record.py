import ssz

from eth2.beacon.types.pending_attestations import PendingAttestation


def test_defaults(sample_pending_attestation_record_params):
    pending_attestation = PendingAttestation(**sample_pending_attestation_record_params)

    assert pending_attestation.data == sample_pending_attestation_record_params["data"]
    assert (
        pending_attestation.aggregation_bits
        == sample_pending_attestation_record_params["aggregation_bits"]
    )  # noqa: E501
    assert (
        pending_attestation.inclusion_delay
        == sample_pending_attestation_record_params["inclusion_delay"]
    )  # noqa: E501
    assert (
        pending_attestation.proposer_index
        == sample_pending_attestation_record_params["proposer_index"]
    )  # noqa: E501
    assert ssz.encode(pending_attestation)
