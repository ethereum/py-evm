from abc import (
    ABC,
    abstractmethod,
)
from collections import (
    UserDict,
)

from typing import (
    Type,
    TYPE_CHECKING,
)

from eth_keys.datatypes import (
    PrivateKey,
    PublicKey,
    NonRecoverableSignature,
)
from eth_keys.exceptions import (
    BadSignature,
)

from eth_utils import (
    keccak,
    ValidationError,
)


if TYPE_CHECKING:
    from p2p.discv5.enr import (  # noqa: F401
        BaseENR,
        ENR,
    )

# https://github.com/python/mypy/issues/5264#issuecomment-399407428
if TYPE_CHECKING:
    IdentitySchemeRegistryBaseType = UserDict[bytes, Type["IdentityScheme"]]
else:
    IdentitySchemeRegistryBaseType = UserDict


class IdentitySchemeRegistry(IdentitySchemeRegistryBaseType):

    def register(self,
                 identity_scheme_class: Type["IdentityScheme"]
                 ) -> Type["IdentityScheme"]:
        """Class decorator to register identity schemes."""
        if identity_scheme_class.id is None:
            raise ValueError("Identity schemes must define ID")

        if identity_scheme_class.id in self:
            raise ValueError(
                f"Identity scheme with id {identity_scheme_class.id} is already registered",
            )

        self[identity_scheme_class.id] = identity_scheme_class

        return identity_scheme_class


default_identity_scheme_registry = IdentitySchemeRegistry()


class IdentityScheme(ABC):

    id: bytes = None

    @classmethod
    @abstractmethod
    def create_signature(cls, enr: "BaseENR", private_key: bytes) -> bytes:
        pass

    @classmethod
    @abstractmethod
    def validate_signature(cls, enr: "ENR") -> None:
        pass

    @classmethod
    @abstractmethod
    def extract_node_address(cls, enr: "ENR") -> bytes:
        pass


@default_identity_scheme_registry.register
class V4IdentityScheme(IdentityScheme):

    id = b"v4"
    public_key_enr_key = b"secp256k1"

    @classmethod
    def create_signature(cls, enr: "BaseENR", private_key: bytes) -> bytes:
        message = enr.get_signing_message()
        private_key_object = PrivateKey(private_key)
        signature = private_key_object.sign_msg_non_recoverable(message)
        return bytes(signature)

    @classmethod
    def validate_signature(cls, enr: "ENR") -> None:
        public_key = PublicKey.from_compressed_bytes(enr[cls.public_key_enr_key])
        message = enr.get_signing_message()

        try:
            signature = NonRecoverableSignature(enr.signature)
        except BadSignature:
            is_valid = False
        else:
            is_valid = signature.verify_msg(message, public_key)

        if not is_valid:
            raise ValidationError("Invalid signature")

    @classmethod
    def extract_node_address(cls, enr: "ENR") -> bytes:
        public_key = PublicKey.from_compressed_bytes(enr[cls.public_key_enr_key])
        return keccak(public_key.to_bytes())
