from typing import (
    Sequence,
    Type,
)

from eth_typing import (
    BLSPubkey,
    BLSSignature,
    Hash32,
)

from eth2.beacon.exceptions import (
    SignatureError,
)

from .backends import (
    DEFAULT_BACKEND,
    NoOpBackend,
)
from .backends.base import (
    BaseBLSBackend,
)
from .validation import (
    validate_private_key,
    validate_signature,
)


class Eth2BLS:
    backend: Type[BaseBLSBackend]

    def __init__(self) -> None:
        self.use_default_backend()

    @classmethod
    def use(cls, backend: Type[BaseBLSBackend]) -> None:
        cls.backend = backend

    @classmethod
    def use_default_backend(cls) -> None:
        cls.use(DEFAULT_BACKEND)

    @classmethod
    def use_noop_backend(cls) -> None:
        cls.use(NoOpBackend)

    @classmethod
    def privtopub(cls,
                  privkey: int) -> BLSPubkey:
        validate_private_key(privkey)
        return cls.backend.privtopub(privkey)

    @classmethod
    def sign(cls,
             message_hash: Hash32,
             privkey: int,
             domain: int) -> BLSSignature:
        validate_private_key(privkey)
        return cls.backend.sign(message_hash, privkey, domain)

    @classmethod
    def aggregate_signatures(cls,
                             signatures: Sequence[BLSSignature]) -> BLSSignature:
        return cls.backend.aggregate_signatures(signatures)

    @classmethod
    def aggregate_pubkeys(cls,
                          pubkeys: Sequence[BLSPubkey]) -> BLSPubkey:
        return cls.backend.aggregate_pubkeys(pubkeys)

    @classmethod
    def verify(cls,
               message_hash: Hash32,
               pubkey: BLSPubkey,
               signature: BLSSignature,
               domain: int) -> bool:
        if cls.backend != NoOpBackend:
            validate_signature(signature)
        return cls.backend.verify(message_hash, pubkey, signature, domain)

    @classmethod
    def verify_multiple(cls,
                        pubkeys: Sequence[BLSPubkey],
                        message_hashes: Sequence[Hash32],
                        signature: BLSSignature,
                        domain: int) -> bool:
        if cls.backend != NoOpBackend:
            validate_signature(signature)
        return cls.backend.verify_multiple(pubkeys, message_hashes, signature, domain)

    @classmethod
    def validate(cls,
                 message_hash: Hash32,
                 pubkey: BLSPubkey,
                 signature: BLSSignature,
                 domain: int) -> None:
        if not cls.verify(message_hash, pubkey, signature, domain):
            raise SignatureError(
                f"backend {cls.backend.__name__}\n"
                f"message_hash {message_hash}\n"
                f"pubkey {pubkey}\n"
                f"signature {signature}\n"
                f"domain {domain}"
            )

    @classmethod
    def validate_multiple(cls,
                          pubkeys: Sequence[BLSPubkey],
                          message_hashes: Sequence[Hash32],
                          signature: BLSSignature,
                          domain: int) -> None:
        if not cls.verify_multiple(pubkeys, message_hashes, signature, domain):
            raise SignatureError(
                f"backend {cls.backend.__name__}\n"
                f"pubkeys {pubkeys}\n"
                f"message_hashes {message_hashes}\n"
                f"signature {signature}\n"
                f"domain {domain}"
            )


bls = Eth2BLS()
