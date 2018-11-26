import pytest

from eth.beacon.types.attestation_signed_data import (
    AttestationSignedData,
)


@pytest.mark.parametrize(
    'param,default_value',
    [
        ('parent_hashes', ()),
    ]
)
def test_defaults(param, default_value, sample_attestation_signed_data_params):
    del sample_attestation_signed_data_params[param]
    attestation_signed_data = AttestationSignedData(**sample_attestation_signed_data_params)

    assert getattr(attestation_signed_data, param) == default_value
