from __future__ import absolute_import
import os
import pytest
from evm.ecc.backends.pure_python import PurePythonECCBackend
from evm.ecc import (
    get_ecc_backend,
)
from evm.utils.secp256k1 import (
    decode_public_key,
)


PRIVATE_KEY = ( 
    b'E\xa9\x15\xe4\xd0`\x14\x9e\xb46Y`\xe6\xa7\xa4_3C\x93\t0a\x11k\x19~2@\x06_\xf2\xd8'
)
PUBLIC_KEY = ( 
    b'\x04:QAvFo\xa8\x15\xedH\x1f\xfa\xd0\x91\x10\xa2\xd3D\xf6\xc9\xb7\x8c\x1d\x14\xaf\xc3Q\xc3\xa5\x1b\xe3=\x80r\xe7y9\xdc\x03\xbaDy\x07y\xb7\xa1\x02[\xaf0\x03\xf6s$0\xe2\x0c\xd9\xb7m\x953\x91\xb3'
)
RAW_PUBLIC_KEY = decode_public_key(PUBLIC_KEY)

MSG = b'my message'
MSG_HASH = b'#tpO\xbbmDaqK\xcb\xab\xebj\x16\x0c"E\x9ex\x1b\x08\\\x83lI\x08JG\x0e\xd6\xa4'

SIGNATURE = ( 
    b'\x1bw\x84\xe4V\x19\x85\xaf\xeaj\xa9q\x9b\xcf\xc2\xbf\x17\x0c\x8c\xd7\xc3\xd5\xc0\x11\xbd\x80A\xc8\xdbJ\x97\x83\x07[\xb1\xdaD\x00\xe1\xd9#W\x83\rF\xa5gx\xc9"\xdem\xbfu\xa2\x19\xfe\xc6\x83IM\xc7o\xfd\x7f'
)

V = 27
R = 54060028713369731575288880898058519584012347418583874062392262086259746767623
S = 41474707565615897636207177895621376369577110960831782659442889110043833138559

pytest.importorskip('coincurve') 
purePython = PurePythonECCBackend()


def test_ecdsa_sign():
    # Sets ecc backend to coin curve
    os.environ['EVM_ECC_BACKEND_CLASS'] = 'evm.ecc.backends.coincurve.CoinCurveECCBackend'
    assert get_ecc_backend().ecdsa_sign(MSG, PRIVATE_KEY) == purePython.ecdsa_sign(MSG, PRIVATE_KEY)


def test_ecdsa_raw_sign():
    assert get_ecc_backend().ecdsa_raw_sign(MSG_HASH, PRIVATE_KEY) == purePython.ecdsa_raw_sign(MSG_HASH, PRIVATE_KEY)


def test_ecdsa_verify():
    assert get_ecc_backend().ecdsa_verify(MSG, SIGNATURE, PUBLIC_KEY) == purePython.ecdsa_verify(MSG, SIGNATURE, PUBLIC_KEY)


def test_ecdsa_raw_verify():
    assert get_ecc_backend().ecdsa_raw_verify(MSG_HASH, (V, R, S), RAW_PUBLIC_KEY) == purePython.ecdsa_raw_verify(MSG_HASH, (V, R, S), RAW_PUBLIC_KEY)

def test_ecdsa_recover():
    assert get_ecc_backend().ecdsa_recover(MSG, SIGNATURE) == purePython.ecdsa_recover(MSG, SIGNATURE)


def test_ecdsa_raw_recover():
    assert get_ecc_backend().ecdsa_raw_recover(MSG_HASH, (V, R, S)) == purePython.ecdsa_raw_recover(MSG_HASH, (V, R, S))
    # Switches ecc backend back to pure python for the rest of the tests
    os.environ['EVM_ECC_BACKEND_CLASS'] = 'evm.ecc.backends.pure_python.PurePythonECCBackend'