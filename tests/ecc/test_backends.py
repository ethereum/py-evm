import pytest

from evm.ecc.backends.pure_python import PurePythonECCBackend
from evm.ecc.backends.coincurve import CoinCurveECCBackend
from evm.utils.ecdsa import decode_signature
from evm.utils.secp256k1 import (
    decode_public_key,
    encode_raw_public_key,
)

from tests.ecdsa_fixtures import (
    MSG,
    MSGHASH,
    SECRETS,
)


backends = [PurePythonECCBackend()]
try:
    backends.append(CoinCurveECCBackend())
except ImportError:
    pass


@pytest.mark.parametrize("backend", backends)
@pytest.mark.parametrize("label, d", sorted(SECRETS.items()))
def test_ecdsa_sign(backend, label, d):
    assert backend.ecdsa_sign(MSG, d['privkey']) == d['sig']


@pytest.mark.parametrize("backend", backends)
@pytest.mark.parametrize("label, d", sorted(SECRETS.items()))
def test_ecdsa_raw_sign(backend, label, d):
    assert backend.ecdsa_raw_sign(MSGHASH, d['privkey']) == d['raw_sig']


@pytest.mark.parametrize("backend", backends)
@pytest.mark.parametrize("label, d", sorted(SECRETS.items()))
def test_ecdsa_verify(backend, label, d):
    assert backend.ecdsa_verify(MSG, d['sig'], d['pubkey'])


@pytest.mark.parametrize("backend", backends)
@pytest.mark.parametrize("label, d", sorted(SECRETS.items()))
def test_ecdsa_raw_verify(backend, label, d):
    assert backend.ecdsa_raw_verify(
        MSGHASH, decode_signature(d['sig']), decode_public_key(d['pubkey']))


@pytest.mark.parametrize("backend", backends)
@pytest.mark.parametrize("label, d", sorted(SECRETS.items()))
def test_ecdsa_recover(backend, label, d):
    pubkey = backend.ecdsa_recover(MSG, d['sig'])
    assert pubkey == d['pubkey']


@pytest.mark.parametrize("backend", backends)
@pytest.mark.parametrize("label, d", sorted(SECRETS.items()))
def test_ecdsa_raw_recover(backend, label, d):
    raw_public_key = backend.ecdsa_raw_recover(MSGHASH, d['raw_sig'])
    assert encode_raw_public_key(raw_public_key) == d['pubkey']
