from .base import BaseECCBackend

from evm.utils.ecdsa import (
    decode_signature,
    encode_signature,
)

from evm.utils.keccak import (
    keccak,
)

from evm.utils.secp256k1 import decode_public_key


class CoinCurveECCBackend(BaseECCBackend):
    def __init__(self):
        try:
            import coincurve
        except ImportError:
            raise ImportError("The CoinCurveECCBackend requires the coincurve \
                               library which is not available for import.")
        self.keys = coincurve.keys
        self.ecdsa = coincurve.ecdsa

    def ecdsa_sign(self, msg, private_key):
        v, r, s = self.ecdsa_raw_sign(keccak(msg), private_key)
        signature = encode_signature(v, r, s)
        return signature

    def ecdsa_raw_sign(self, msg_hash, private_key):
        signature = self.keys.PrivateKey(private_key).sign_recoverable(msg_hash, hasher=None)
        return decode_signature(signature)

    def ecdsa_verify(self, msg, signature, public_key):
        return self.ecdsa_recover(msg, signature) == public_key

    def ecdsa_raw_verify(self, msg_hash, vrs, raw_public_key):
        return self.ecdsa_raw_recover(msg_hash, vrs) == raw_public_key

    def ecdsa_recover(self, msg, signature):
        return self.keys.PublicKey.from_signature_and_message(
            signature, msg, hasher=keccak).format(compressed=False)[1:]

    def ecdsa_raw_recover(self, msg_hash, vrs):
        signature = encode_signature(*vrs)
        public_key = self.keys.PublicKey.from_signature_and_message(
            signature, msg_hash, hasher=None).format(compressed=False)[1:]
        return decode_public_key(public_key)
