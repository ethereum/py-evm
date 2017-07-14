"""
Functions lifted from https://github.com/vbuterin/pybitcointools
"""
import hashlib
import hmac

from evm.constants import (
    SECPK1_N as N,
    SECPK1_G as G,
    SECPK1_Gx as Gx,
    SECPK1_Gy as Gy,
    SECPK1_P as P,
    SECPK1_A as A,
    SECPK1_B as B,
)

from .address import (
    public_key_to_address,
)
from .keccak import (
    keccak,
)
from .jacobian import (
    inv,
    fast_multiply,
    fast_add,
    jacobian_add,
    jacobian_multiply,
    from_jacobian,
)
from .numeric import (
    int_to_byte,
    int_to_big_endian,
    big_endian_to_int,
)
from .padding import pad32
from .secp256k1 import (
    decode_public_key,
    encode_raw_public_key,
    private_key_to_public_key,
)


class BadSignature(ValueError):
    """
    Raised for invalid signatures.
    """
    pass


def encode_signature(v, r, s):
    vb = int_to_byte(v)
    rb = pad32(int_to_big_endian(r))
    sb = pad32(int_to_big_endian(s))

    return b''.join((vb, rb, sb))


def decode_signature(signature):
    if not isinstance(signature, bytes):
        raise TypeError("signature parameter must be bytes")
    if not len(signature) == 65:
        raise BadSignature(
            "signature must be exactly 65 bytes in length: got {0}".format(len(signature))
        )

    rb = signature[1:33]
    sb = signature[33:65]

    v = signature[0]
    r = big_endian_to_int(rb)
    s = big_endian_to_int(sb)

    return v, r, s


def deterministic_generate_k(msg_hash, private_key, digest_fn=hashlib.sha256):
    if not isinstance(msg_hash, bytes):
        raise TypeError("msg_hash parameter must be bytes")
    if not isinstance(private_key, bytes):
        raise TypeError("private_key parameter must be bytes")

    v_0 = b'\x01' * 32
    k_0 = b'\x00' * 32

    k_1 = hmac.new(k_0, v_0 + b'\x00' + private_key + msg_hash, digest_fn).digest()
    v_1 = hmac.new(k_1, v_0, digest_fn).digest()
    k_2 = hmac.new(k_1, v_1 + b'\x01' + private_key + msg_hash, digest_fn).digest()
    v_2 = hmac.new(k_2, v_1, digest_fn).digest()

    kb = hmac.new(k_2, v_2, digest_fn).digest()
    k = big_endian_to_int(kb)
    return k


def ecdsa_raw_sign(msg_hash, private_key):
    if not isinstance(msg_hash, bytes):
        raise TypeError("msg_hash parameter must be bytes")
    if not isinstance(private_key, bytes):
        raise TypeError("private_key parameter must be bytes")

    z = big_endian_to_int(msg_hash)
    k = deterministic_generate_k(msg_hash, private_key)

    r, y = fast_multiply(G, k)
    s_raw = inv(k, N) * (z + r * big_endian_to_int(private_key)) % N

    v = 27 + ((y % 2) ^ (0 if s_raw * 2 < N else 1))
    s = s_raw if s_raw * 2 < N else N - s_raw

    return v, r, s


def ecdsa_sign(msg, private_key):
    if not isinstance(msg, bytes):
        raise TypeError("msg parameter must be bytes")
    if not isinstance(private_key, bytes):
        raise TypeError("private_key parameter must be bytes")

    v, r, s = ecdsa_raw_sign(keccak(msg), private_key)
    signature = encode_signature(v, r, s)
    if not ecdsa_verify(msg, signature, private_key_to_public_key(private_key)):
        raise BadSignature(
            "Bad Signature: {0}\nv = {1}\nr = {2}\ns = {3}".format(signature, v, r, s)
        )
    return signature


def ecdsa_raw_verify(msg_hash, vrs, raw_public_key):
    if not isinstance(msg_hash, bytes):
        raise TypeError("msg_hash parameter must be bytes")
    if not isinstance(raw_public_key, tuple) or len(raw_public_key) != 2:
        raise TypeError("raw_public_key parameter must be a 2-tuple of integers")

    v, r, s = vrs
    if not (27 <= v <= 34):
        raise BadSignature("Invalid Signature")

    w = inv(s, N)
    z = big_endian_to_int(msg_hash)

    u1, u2 = z * w % N, r * w % N
    x, y = fast_add(
        fast_multiply(G, u1),
        fast_multiply(raw_public_key, u2),
    )
    return bool(r == x and (r % N) and (s % N))


def ecdsa_verify_address(msg, signature, address):
    if not isinstance(msg, bytes):
        raise TypeError("msg parameter must be bytes")
    if not isinstance(signature, bytes):
        raise TypeError("signature parameter must be bytes")
    if not isinstance(address, bytes) or len(address) != 20:
        raise TypeError("address must be bytes of length 20")

    public_key = ecdsa_recover(msg, signature)
    recovered_address = public_key_to_address(public_key)
    return recovered_address == address


def ecdsa_verify(msg, signature, public_key):
    if not isinstance(msg, bytes):
        raise TypeError("msg parameter must be bytes")
    if not isinstance(signature, bytes):
        raise TypeError("signature parameter must be bytes")
    if not isinstance(public_key, bytes):
        raise TypeError("public_key parameter must be bytes")

    return ecdsa_raw_verify(
        keccak(msg),
        decode_signature(signature),
        decode_public_key(public_key),
    )


def ecdsa_raw_recover(msg_hash, vrs):
    if not isinstance(msg_hash, bytes):
        raise TypeError("msg_hash parameter must be bytes")

    v, r, s = vrs

    if not (27 <= v <= 34):
        raise BadSignature("%d must in range 27-31" % v)

    x = r

    xcubedaxb = (x * x * x + A * x + B) % P
    beta = pow(xcubedaxb, (P + 1) // 4, P)
    y = beta if v % 2 ^ beta % 2 else (P - beta)
    # If xcubedaxb is not a quadratic residue, then r cannot be the x coord
    # for a point on the curve, and so the sig is invalid
    if (xcubedaxb - y * y) % P != 0 or not (r % N) or not (s % N):
        raise BadSignature("Invalid signature")
    z = big_endian_to_int(msg_hash)
    Gz = jacobian_multiply((Gx, Gy, 1), (N - z) % N)
    XY = jacobian_multiply((x, y, 1), s)
    Qr = jacobian_add(Gz, XY)
    Q = jacobian_multiply(Qr, inv(r, N))
    Q = from_jacobian(Q)

    return Q


def ecdsa_recover(msg, signature):
    if not isinstance(msg, bytes):
        raise TypeError("msg parameter must be bytes")
    if not isinstance(signature, bytes):
        raise TypeError("signature parameter must be bytes")

    v, r, s = decode_signature(signature)
    raw_public_key = ecdsa_raw_recover(keccak(msg), (v, r, s))
    return encode_raw_public_key(raw_public_key)
