from evm.utils.ecdsa import (
    ecdsa_raw_recover,
    ecdsa_raw_sign,
    ecdsa_raw_verify,
    ecdsa_recover,
    ecdsa_sign,
    ecdsa_verify,
)

from .base import BaseECCBackend


class PurePythonECCBackend(BaseECCBackend):
    def ecdsa_sign(self, msg, private_key):
        return ecdsa_sign(msg, private_key)

    def ecdsa_raw_sign(self, msg_hash, private_key):
        return ecdsa_raw_sign(msg_hash, private_key)

    def ecdsa_verify(self, msg, signature, public_key):
        return ecdsa_verify(msg, signature, public_key)

    def ecdsa_raw_verify(self, msg_hash, vrs, raw_public_key):
        return ecdsa_raw_verify(msg_hash, vrs, raw_public_key)

    def ecdsa_recover(self, msg, signature):
        return ecdsa_recover(msg, signature)

    def ecdsa_raw_recover(self, msg_hash, vrs):
        return ecdsa_raw_recover(msg_hash, vrs)
