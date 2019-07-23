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
    ValidationError as EthKeysValidationError,
)

from eth_utils import (
    encode_hex,
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
    def create_enr_signature(cls, enr: "BaseENR", private_key: bytes) -> bytes:
        """Create and return the signature for an ENR."""
        pass

    @classmethod
    @abstractmethod
    def validate_enr_structure(cls, enr: "BaseENR") -> None:
        """Validate that the data required by the identity scheme is present and valid in an ENR."""
        pass

    @classmethod
    @abstractmethod
    def validate_enr_signature(cls, enr: "ENR") -> None:
        """Validate the signature of an ENR."""
        pass

    @classmethod
    @abstractmethod
    def extract_public_key(cls, enr: "BaseENR") -> bytes:
        """Retrieve the public key from an ENR."""
        pass

    @classmethod
    @abstractmethod
    def extract_node_id(cls, enr: "BaseENR") -> bytes:
        """Retrieve the node id from an ENR."""
        pass


@default_identity_scheme_registry.register
class V4IdentityScheme(IdentityScheme):

    id = b"v4"
    public_key_enr_key = b"secp256k1"

    @classmethod
    def create_enr_signature(cls, enr: "BaseENR", private_key: bytes) -> bytes:
        message = enr.get_signing_message()
        private_key_object = PrivateKey(private_key)
        signature = private_key_object.sign_msg_non_recoverable(message)
        return bytes(signature)

    @classmethod
    def validate_enr_structure(cls, enr: "BaseENR") -> None:
        if cls.public_key_enr_key not in enr:
            raise ValidationError(f"ENR is missing required key {cls.public_key_enr_key}")

        public_key = cls.extract_public_key(enr)
        try:
            PublicKey.from_compressed_bytes(public_key)
        except EthKeysValidationError as error:
            raise ValidationError(
                f"ENR public key {encode_hex(public_key)} is invalid: {error}"
            ) from error

    @classmethod
    def validate_enr_signature(cls, enr: "ENR") -> None:
        public_key_object = PublicKey.from_compressed_bytes(enr.public_key)
        message = enr.get_signing_message()

        try:
            signature = NonRecoverableSignature(enr.signature)
        except BadSignature:
            is_valid = False
        else:
            is_valid = signature.verify_msg(message, public_key_object)

        if not is_valid:
            raise ValidationError("Invalid signature")

    @classmethod
    def extract_public_key(cls, enr: "BaseENR") -> bytes:
        return enr[cls.public_key_enr_key]

    @classmethod
    def extract_node_id(cls, enr: "BaseENR") -> bytes:
        public_key_object = PublicKey.from_compressed_bytes(enr.public_key)
        uncompressed_bytes = public_key_object.to_bytes()
        return keccak(uncompressed_bytes)
