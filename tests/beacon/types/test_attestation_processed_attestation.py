from eth.beacon.types.processed_attestation import (
    ProcessedAttestation,
)


def test_defaults(sample_processed_attestation_params):
    attestation_record = ProcessedAttestation(**sample_processed_attestation_params)

    assert attestation_record.data == sample_processed_attestation_params['data']
    assert attestation_record.attester_bitfield == sample_processed_attestation_params['attester_bitfield']  # noqa: E501
    assert attestation_record.poc_bitfield == sample_processed_attestation_params['poc_bitfield']
    assert attestation_record.slot_included == sample_processed_attestation_params['slot_included']
