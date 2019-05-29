import pytest

from hypothesis import (
    given,
    strategies as st,
)

from eth_utils import (
    ValidationError,
)

from p2p.exceptions import (
    DecryptionError,
)
from p2p.discv5.encryption import (
    aesgcm_encrypt,
    aesgcm_decrypt,
    validate_aes128_key,
    validate_nonce,
    AES128Key,
    Nonce,
)
from p2p.discv5.constants import (
    AES128_KEY_SIZE,
    NONCE_SIZE,
)


key_st = st.binary(min_size=AES128_KEY_SIZE, max_size=AES128_KEY_SIZE)
nonce_st = st.binary(min_size=NONCE_SIZE, max_size=NONCE_SIZE)
plain_text_st = st.binary(min_size=0, max_size=10)
aad_st = st.binary(min_size=0, max_size=10)


def test_key_validation_invalid():
    for length in (0, 12, 15, 17, 32):
        with pytest.raises(ValidationError):
            validate_aes128_key(AES128Key(b"\x00" * length))


@given(key_st)
def test_key_validation_valid(key):
    validate_aes128_key(AES128Key(key))


def test_nonce_validation_invalid():
    for length in (0, 11, 13, 16):
        with pytest.raises(ValidationError):
            validate_nonce(Nonce(b"\x00" * length))


@given(nonce_st)
def test_nonce_validation_valid(key):
    validate_nonce(Nonce(key))


def test_decryption_with_wrong_inputs():
    key = AES128Key(b"\x00" * 16)
    nonce = Nonce(b"\x11" * 12)
    plain_text = b"\x33" * 5
    aad = b"\x44" * 5
    cipher_text = aesgcm_encrypt(key, nonce, plain_text, aad)

    assert aesgcm_decrypt(key, nonce, cipher_text, aad) == plain_text
    with pytest.raises(ValidationError):
        aesgcm_decrypt(b"", nonce, cipher_text, aad)
    with pytest.raises(ValidationError):
        aesgcm_decrypt(key, b"", cipher_text, aad)
    with pytest.raises(DecryptionError):
        aesgcm_decrypt(key, nonce, b"", aad)
    with pytest.raises(DecryptionError):
        aesgcm_decrypt(key, nonce, cipher_text, b"")


@given(
    key=key_st,
    nonce=nonce_st,
    plain_text=plain_text_st,
    aad=aad_st,
)
def test_roundtrip(key, nonce, plain_text, aad):
    cipher_text = aesgcm_encrypt(key, nonce, plain_text, aad)
    plain_text_recovered = aesgcm_decrypt(key, nonce, cipher_text, aad)
    assert plain_text_recovered == plain_text
