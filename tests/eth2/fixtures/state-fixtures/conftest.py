import pytest
from eth2._utils.bls import bls
from eth2._utils.bls.backends import PyECCBackend
from eth2.beacon.operations.attestation_pool import AttestationPool


#
# BLS mock
#
@pytest.fixture(autouse=True)
def mock_bls(mocker, request):
    if "noautofixture" in request.keywords:
        bls.use(PyECCBackend)
    else:
        bls.use_noop_backend()


#
# Attestation pool
#
@pytest.fixture
def empty_attestation_pool():
    return AttestationPool()
