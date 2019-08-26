from eth2.beacon.types.attestation_data import AttestationData


def test_defaults(sample_attestation_data_params):
    attestation_data = AttestationData(**sample_attestation_data_params)

    assert (
        attestation_data.source.epoch == sample_attestation_data_params["source"].epoch
    )
