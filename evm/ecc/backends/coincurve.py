from .base import BaseECCBackend

from evm.utils.ecdsa import (
    encode_signature,
)

from evm.utils.numeric import (
    big_endian_to_int,
    safe_ord
)

from evm.constants import (
    NULL_BYTE,
)

from evm.utils.keccak import (
    keccak,
)

from evm.utils.secp256k1 import (
    decode_public_key,
    encode_raw_public_key,
)


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
        v = safe_ord(signature[64]) + 27
        r = big_endian_to_int(signature[0:32])
        s = big_endian_to_int(signature[32:64])
        return v, r, s

    def ecdsa_verify(self, msg, signature, public_key):
        signature = signature[1:] + NULL_BYTE
        signature = self.__recoverable_to_normal(signature)
        return self.keys.PublicKey(public_key).verify(signature, msg, hasher=keccak)

    def ecdsa_raw_verify(self, msg_hash, vrs, raw_public_key):
        v, r, s = vrs
        signature = encode_signature(v, r, s)[1:] + NULL_BYTE
        signature = self.__recoverable_to_normal(signature)
        public_key = encode_raw_public_key(raw_public_key)
        return self.keys.PublicKey(public_key).verify(signature, msg_hash, hasher=None)

    def ecdsa_recover(self, msg, signature):
        signature = signature[1:] + NULL_BYTE
        return self.keys.PublicKey.from_signature_and_message(signature,
                                                              msg,
                                                              hasher=keccak
                                                              ).format(compressed=False)

    def ecdsa_raw_recover(self, msg_hash, vrs):
        v, r, s = vrs
        signature = encode_signature(v, r, s)[1:] + NULL_BYTE
        raw_public_key = self.keys.PublicKey.from_signature_and_message(signature,
                                                                        msg_hash,
                                                                        hasher=None
                                                                        ).format(compressed=False)
        return decode_public_key(raw_public_key)

    def __recoverable_to_normal(self, signature):
        return self.ecdsa.cdata_to_der(
            self.ecdsa.recoverable_convert(
                self.ecdsa.deserialize_recoverable(signature)
            )
        )
