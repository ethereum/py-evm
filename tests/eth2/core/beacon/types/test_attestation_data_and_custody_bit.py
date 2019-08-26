from eth2.beacon.types.attestation_data_and_custody_bits import (
    AttestationDataAndCustodyBit,
)


def test_defaults(sample_attestation_data_and_custody_bit_params):
    params = sample_attestation_data_and_custody_bit_params
    attestation_data_and_custody_bit = AttestationDataAndCustodyBit(**params)

    assert attestation_data_and_custody_bit.data == params["data"]
    assert attestation_data_and_custody_bit.custody_bit == params["custody_bit"]
