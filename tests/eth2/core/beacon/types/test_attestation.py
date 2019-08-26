import pytest
import ssz

from eth2.beacon.types.attestations import Attestation


@pytest.mark.parametrize("param,default_value", [("signature", b"\x00" * 96)])
def test_defaults(param, default_value, sample_attestation_params):
    del sample_attestation_params[param]
    attestation = Attestation(**sample_attestation_params)

    assert getattr(attestation, param) == default_value
    assert ssz.encode(attestation)
