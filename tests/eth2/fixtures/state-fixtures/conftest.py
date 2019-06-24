import pytest
from eth2._utils.bls import bls
from eth2._utils.bls.backends import PyECCBackend


#
# BLS mock
#
@pytest.fixture(autouse=True)
def mock_bls(mocker, request):
    if 'noautofixture' in request.keywords:
        bls.use(PyECCBackend)
    else:
        bls.use_noop_backend()
