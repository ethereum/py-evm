import os
import struct
from hashlib import sha256
from typing import cast

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.constant_time import bytes_eq

from eth_utils import (
    int_to_big_endian,
)

from eth_keys import keys
from eth_keys import datatypes

from evm.utils.padding import (
    pad32,
)

from p2p.exceptions import DecryptionError

from .constants import (
    PUBKEY_LEN,
)


CIPHER = algorithms.AES
MODE = modes.CTR
CURVE = ec.SECP256K1()
# ECIES using AES256 and HMAC-SHA-256-32
KEY_LEN = 32


def generate_privkey():
    """Generate a new SECP256K1 private key and return it"""
    privkey = ec.generate_private_key(CURVE, default_backend())
    return keys.PrivateKey(pad32(int_to_big_endian(privkey.private_numbers().private_value)))


def ecdh_agree(privkey: datatypes.PrivateKey, pubkey: datatypes.PublicKey) -> bytes:
    """Performs a key exchange operation using the ECDH algorithm."""
    privkey_as_int = int(cast(int, privkey))
    ec_privkey = ec.derive_private_key(privkey_as_int, CURVE, default_backend())
    pubkey_bytes = b'\x04' + pubkey.to_bytes()
    pubkey_nums = ec.EllipticCurvePublicNumbers.from_encoded_point(CURVE, pubkey_bytes)
    ec_pubkey = pubkey_nums.public_key(default_backend())
    return ec_privkey.exchange(ec.ECDH(), ec_pubkey)


def encrypt(data: bytes, pubkey: datatypes.PublicKey, shared_mac_data: bytes = b'') -> bytes:
    """Encrypt data with ECIES method to the given public key

    1) generate r = random value
    2) generate shared-secret = kdf( ecdhAgree(r, P) )
    3) generate R = rG [same op as generating a public key]
    4) 0x04 || R || AsymmetricEncrypt(shared-secret, plaintext) || tag
    """
    # 1) generate r = random value
    ephemeral = generate_privkey()

    # 2) generate shared-secret = kdf( ecdhAgree(r, P) )
    key_material = ecdh_agree(ephemeral, pubkey)
    key = kdf(key_material)
    key_enc, key_mac = key[:KEY_LEN // 2], key[KEY_LEN // 2:]

    key_mac = sha256(key_mac).digest()
    # 3) generate R = rG [same op as generating a public key]
    ephem_pubkey = ephemeral.public_key

    # Encrypt
    algo = CIPHER(key_enc)
    iv = os.urandom(algo.block_size // 8)
    ctx = Cipher(algo, MODE(iv), default_backend()).encryptor()
    ciphertext = ctx.update(data) + ctx.finalize()

    # 4) 0x04 || R || AsymmetricEncrypt(shared-secret, plaintext) || tag
    msg = b'\x04' + ephem_pubkey.to_bytes() + iv + ciphertext

    # the MAC of a message (called the tag) as per SEC 1, 3.5.
    tag = hmac_sha256(key_mac, msg[1 + PUBKEY_LEN:] + shared_mac_data)
    return msg + tag


def decrypt(data: bytes, privkey: datatypes.PrivateKey, shared_mac_data: bytes = b'') -> bytes:
    """Decrypt data with ECIES method using the given private key

    1) generate shared-secret = kdf( ecdhAgree(myPrivKey, msg[1:65]) )
    2) verify tag
    3) decrypt

    ecdhAgree(r, recipientPublic) == ecdhAgree(recipientPrivate, R)
    [where R = r*G, and recipientPublic = recipientPrivate*G]

    """
    if data[:1] != b'\x04':
        raise DecryptionError("wrong ecies header")

    #  1) generate shared-secret = kdf( ecdhAgree(myPrivKey, msg[1:65]) )
    shared = data[1:1 + PUBKEY_LEN]
    key_material = ecdh_agree(privkey, keys.PublicKey(shared))
    key = kdf(key_material)
    key_enc, key_mac = key[:KEY_LEN // 2], key[KEY_LEN // 2:]
    key_mac = sha256(key_mac).digest()
    tag = data[-KEY_LEN:]

    # 2) Verify tag
    expected_tag = hmac_sha256(key_mac, data[1 + PUBKEY_LEN:- KEY_LEN] + shared_mac_data)
    if not bytes_eq(expected_tag, tag):
        raise DecryptionError("Failed to verify tag")

    # 3) Decrypt
    algo = CIPHER(key_enc)
    blocksize = algo.block_size // 8
    iv = data[1 + PUBKEY_LEN:1 + PUBKEY_LEN + blocksize]
    ciphertext = data[1 + PUBKEY_LEN + blocksize:- KEY_LEN]
    ctx = Cipher(algo, MODE(iv), default_backend()).decryptor()
    return ctx.update(ciphertext) + ctx.finalize()


def kdf(key_material):
    """NIST SP 800-56a Concatenation Key Derivation Function (see section 5.8.1).

    Pretty much copied from geth's implementation:
    https://github.com/ethereum/go-ethereum/blob/673007d7aed1d2678ea3277eceb7b55dc29cf092/crypto/ecies/ecies.go#L167
    """
    key = b""
    hash_blocksize = hashes.SHA256().block_size
    reps = ((KEY_LEN + 7) * 8) / (hash_blocksize * 8)
    counter = 0
    while counter <= reps:
        counter += 1
        ctx = sha256()
        ctx.update(struct.pack('>I', counter))
        ctx.update(key_material)
        key += ctx.digest()
    return key[:KEY_LEN]


def hmac_sha256(key, msg):
    mac = hmac.HMAC(key, hashes.SHA256(), default_backend())
    mac.update(msg)
    return mac.finalize()
