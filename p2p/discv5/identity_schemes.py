from abc import (
    ABC,
    abstractmethod,
)
from collections import (
    UserDict,
)
import secrets
from typing import (
    Tuple,
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

from p2p.discv5.typing import (
    AES128Key,
    IDNonce,
    NodeID,
    SessionKeys,
)
from p2p.discv5.constants import (
    AES128_KEY_SIZE,
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

    #
    # ENR
    #
    @classmethod
    @abstractmethod
    def create_enr_signature(cls, enr: "BaseENR", private_key: bytes) -> bytes:
        """Create and return the signature for an ENR."""
        ...

    @classmethod
    @abstractmethod
    def validate_enr_structure(cls, enr: "BaseENR") -> None:
        """Validate that the data required by the identity scheme is present and valid in an ENR."""
        ...

    @classmethod
    @abstractmethod
    def validate_enr_signature(cls, enr: "ENR") -> None:
        """Validate the signature of an ENR."""
        ...

    @classmethod
    @abstractmethod
    def extract_public_key(cls, enr: "BaseENR") -> bytes:
        """Retrieve the public key from an ENR."""
        ...

    @classmethod
    @abstractmethod
    def extract_node_id(cls, enr: "BaseENR") -> NodeID:
        """Retrieve the node id from an ENR."""
        ...

    #
    # Handshake
    #
    @classmethod
    @abstractmethod
    def create_handshake_key_pair(cls) -> Tuple[bytes, bytes]:
        """Create a random private/public key pair used for performing a handshake."""
        ...

    @classmethod
    @abstractmethod
    def validate_handshake_public_key(cls, public_key: bytes) -> None:
        """Validate that a public key received during handshake is valid."""
        ...

    @classmethod
    @abstractmethod
    def compute_session_keys(cls,
                             *,
                             local_private_key: bytes,
                             remote_public_key: bytes,
                             local_node_id: NodeID,
                             remote_node_id: NodeID,
                             id_nonce: IDNonce,
                             is_locally_initiated: bool,
                             ) -> SessionKeys:
        """Compute the symmetric session keys."""
        ...

    @classmethod
    @abstractmethod
    def create_id_nonce_signature(cls,
                                  *,
                                  id_nonce: IDNonce,
                                  private_key: bytes,
                                  ) -> bytes:
        """Sign an id nonce received during handshake."""
        ...

    @classmethod
    @abstractmethod
    def validate_id_nonce_signature(cls,
                                    *,
                                    id_nonce: IDNonce,
                                    signature: bytes,
                                    public_key: bytes,
                                    ) -> None:
        """Validate the id nonce signature received from a peer."""
        ...


@default_identity_scheme_registry.register
class V4IdentityScheme(IdentityScheme):

    id = b"v4"
    public_key_enr_key = b"secp256k1"

    private_key_size = 32

    #
    # ENR
    #
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
        cls.validate_public_key(public_key)

    @classmethod
    def validate_enr_signature(cls, enr: "ENR") -> None:
        cls.validate_signature(
            message=enr.get_signing_message(),
            signature=enr.signature,
            public_key=enr.public_key,
        )

    @classmethod
    def extract_public_key(cls, enr: "BaseENR") -> bytes:
        try:
            return enr[cls.public_key_enr_key]
        except KeyError as error:
            raise KeyError("ENR does not contain public key") from error

    @classmethod
    def extract_node_id(cls, enr: "BaseENR") -> NodeID:
        public_key_object = PublicKey.from_compressed_bytes(enr.public_key)
        uncompressed_bytes = public_key_object.to_bytes()
        return NodeID(keccak(uncompressed_bytes))

    #
    # Handshake
    #
    @classmethod
    def create_handshake_key_pair(cls) -> Tuple[bytes, bytes]:
        private_key = secrets.token_bytes(cls.private_key_size)
        public_key = PrivateKey(private_key).public_key.to_compressed_bytes()
        return private_key, public_key

    @classmethod
    def validate_handshake_public_key(cls, public_key: bytes) -> None:
        cls.validate_public_key(public_key)

    @classmethod
    def compute_session_keys(cls,
                             *,
                             local_private_key: bytes,
                             remote_public_key: bytes,
                             local_node_id: NodeID,
                             remote_node_id: NodeID,
                             id_nonce: IDNonce,
                             is_locally_initiated: bool
                             ) -> SessionKeys:
        # TODO: do it properly
        initiator_key = AES128Key(b"\x00" * AES128_KEY_SIZE)
        recipient_key = AES128Key(b"\x11" * AES128_KEY_SIZE)

        if is_locally_initiated:
            encryption_key, decryption_key = initiator_key, recipient_key
        else:
            encryption_key, decryption_key = recipient_key, initiator_key

        return SessionKeys(
            encryption_key=encryption_key,
            decryption_key=decryption_key,
            auth_response_key=AES128Key(b"\x22" * AES128_KEY_SIZE),
        )

    @classmethod
    def create_id_nonce_signature(cls,
                                  *,
                                  id_nonce: IDNonce,
                                  private_key: bytes,
                                  ) -> bytes:
        private_key_object = PrivateKey(private_key)
        signature = private_key_object.sign_msg_non_recoverable(id_nonce)
        return bytes(signature)

    @classmethod
    def validate_id_nonce_signature(cls,
                                    *,
                                    id_nonce: IDNonce,
                                    signature: bytes,
                                    public_key: bytes,
                                    ) -> None:
        cls.validate_signature(
            message=id_nonce,
            signature=signature,
            public_key=public_key,
        )

    #
    # Helpers
    #
    @classmethod
    def validate_public_key(cls, public_key: bytes) -> None:
        try:
            PublicKey.from_compressed_bytes(public_key)
        except (EthKeysValidationError, ValueError) as error:
            raise ValidationError(
                f"Public key {encode_hex(public_key)} is invalid: {error}"
            ) from error

    @classmethod
    def validate_signature(cls, *, message: bytes, signature: bytes, public_key: bytes) -> None:
        public_key_object = PublicKey.from_compressed_bytes(public_key)

        try:
            signature_object = NonRecoverableSignature(signature)
        except BadSignature:
            is_valid = False
        else:
            is_valid = signature_object.verify_msg(message, public_key_object)

        if not is_valid:
            raise ValidationError(
                f"Signature {encode_hex(signature)} is not valid for message {encode_hex(message)} "
                f"and public key {encode_hex(public_key)}"
            )
