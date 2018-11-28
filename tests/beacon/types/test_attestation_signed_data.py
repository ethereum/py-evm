from eth.beacon.types.attestation_signed_data import (
    AttestationSignedData,
)


def test_defaults(sample_attestation_signed_data_params):
    attestation_signed_data = AttestationSignedData(**sample_attestation_signed_data_params)

    assert attestation_signed_data.slot == sample_attestation_signed_data_params['slot']
