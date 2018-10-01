import pytest

from eth.beacon.types.attestation_record import (
    AttestationRecord,
)


@pytest.mark.parametrize(
    'param,default_value',
    [
        ('oblique_parent_hashes', ()),
        ('aggregate_sig', (0, 0)),
    ]
)
def test_defaults(param, default_value, sample_attestation_record_params):
    del sample_attestation_record_params[param]
    attestation_record = AttestationRecord(**sample_attestation_record_params)

    assert getattr(attestation_record, param) == default_value
