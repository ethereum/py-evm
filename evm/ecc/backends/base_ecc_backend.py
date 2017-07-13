class BaseECCBackend(object):
    def ecdsa_sign(self, msg, private_key):
        raise NotImplementedError()

    def ecsdsa_verify(self, msg, signature, public_key):
        raise NotImplementedError()

    def ecdsa_recover(self, msg, signature):
        raise NotImplementedError()

    def ecdsa_raw_recover(self, msg_hash, vrs):
        raise NotImplementedError()

    def ecdsa_raw_sign(self, msg_hash, private_key):
        raise NotImplementedError()

    def encode_signature(self, v, r, s):
        raise NotImplementedError()

    def decode_Signature(self, signature):
        raise NotImplementedError()
