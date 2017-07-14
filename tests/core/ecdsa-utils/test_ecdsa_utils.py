from evm.utils.keccak import (
    keccak,
)
from evm.utils.secp256k1 import (
    decode_public_key,
    encode_raw_public_key,
)
from evm.utils.ecdsa import (
    encode_signature,
    decode_signature,
    ecdsa_sign,
    ecdsa_raw_sign,
    ecdsa_verify,
    ecdsa_raw_verify,
    ecdsa_verify_address,
    ecdsa_recover,
    ecdsa_raw_recover,
)


PRIVATE_KEY = (
    b'E\xa9\x15\xe4\xd0`\x14\x9e\xb46Y`\xe6\xa7\xa4_3C\x93\t0a\x11k\x19~2@\x06_\xf2\xd8'
)
PUBLIC_KEY = (
    b'\x04:QAvFo\xa8\x15\xedH\x1f\xfa\xd0\x91\x10\xa2\xd3D\xf6\xc9\xb7\x8c\x1d\x14\xaf\xc3Q\xc3\xa5\x1b\xe3=\x80r\xe7y9\xdc\x03\xbaDy\x07y\xb7\xa1\x02\x5b\xaf0\x03\xf6s$0\xe2\x0c\xd9\xb7m\x953\x91\xb3'
)
RAW_PUBLIC_KEY = decode_public_key(PUBLIC_KEY)
ADDRESS = (
    b'\xa9OSt\xfc\xe5\xed\xbc\x8e*\x86\x97\xc1S1g~n\xbf\x0b'
)

MSG = b'my message'
MSG_HASH = b'#tpO\xbbmDaqK\xcb\xab\xebj\x16\x0c"E\x9ex\x1b\x08\\\x83lI\x08JG\x0e\xd6\xa4'

V = 27
R = 54060028713369731575288880898058519584012347418583874062392262086259746767623
S = 41474707565615897636207177895621376369577110960831782659442889110043833138559


assert keccak(MSG) == MSG_HASH


assert encode_raw_public_key(decode_public_key(PUBLIC_KEY)) == PUBLIC_KEY


def test_raw_signing():
    v, r, s = ecdsa_raw_sign(MSG_HASH, PRIVATE_KEY)
    assert ecdsa_raw_verify(MSG_HASH, (v, r, s), RAW_PUBLIC_KEY)


def test_raw_recover():
    raw_public_key = ecdsa_raw_recover(MSG_HASH, (V, R, S))
    recovered_public_key = encode_raw_public_key(raw_public_key)
    assert recovered_public_key == PUBLIC_KEY


def test_raw_verify():
    assert ecdsa_raw_verify(MSG_HASH, (V, R, S), RAW_PUBLIC_KEY)


def test_signature_encoding_and_decoding():
    signature = encode_signature(V, R, S)
    v, r, s, = decode_signature(signature)
    assert v == V
    assert r == R
    assert s == S


def test_signing_and_verifying_with_public_key():
    signature = ecdsa_sign(MSG, PRIVATE_KEY)
    assert ecdsa_verify(MSG, signature, PUBLIC_KEY)


def test_signing_and_verifying_with_address():
    signature = ecdsa_sign(MSG, PRIVATE_KEY)
    assert ecdsa_verify_address(MSG, signature, ADDRESS)


def test_recovering_public_key():
    signature = ecdsa_sign(MSG, PRIVATE_KEY)
    recovered_public_key = ecdsa_recover(MSG, signature)
    assert recovered_public_key == PUBLIC_KEY
