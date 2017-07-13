from .base_ecc_backend import BaseECCBackend
from evm.utils.ecdsa import (
    ecdsa_sign,
    ecdsa_verify,
    ecdsa_recover,
    ecdsa_raw_recover,
    ecdsa_raw_sign,
    decode_signature,
    encode_signature,
)


class PurePythonECCBackend(BaseECCBackend):
    def ecdsa_sign(self, msg, private_key):
        return ecdsa_sign(msg, private_key)

    def ecdsa_verify(self, msg, signature, public_key):
        return ecdsa_verify(msg, signature, public_key)

    def ecdsa_recover(self, msg, signature):
        return ecdsa_recover(msg, signature)

    def ecdsa_raw_recover(self, msg_hash, vrs):
        return ecdsa_raw_recover(msg_hash, vrs)

    def ecdsa_raw_sign(self, msg_hash, private_key):
        return ecdsa_raw_sign(msg_hash, hash, private_key)

    def encode_signature(self, v, r, s):
        return encode_signature(v, r, s)

    def decode_signature(self, signature):
        return decode_signature(signature)
