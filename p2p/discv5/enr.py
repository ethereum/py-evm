from abc import (
    ABC,
    abstractmethod,
)
import base64
import collections
from typing import (
    Any,
    AbstractSet,
    Iterable,
    Iterator,
    Mapping,
    Tuple,
    Type,
    Sequence,
    ValuesView,
)
import operator

import rlp
from rlp.exceptions import (
    DeserializationError,
)
from rlp.sedes import (
    big_endian_int,
    binary,
    Binary,
)

from eth_utils import (
    to_dict,
    ValidationError,
)
from eth_utils.toolz import (
    cons,
    interleave,
)

from p2p.discv5.identity_schemes import (
    default_identity_scheme_registry as default_id_scheme_registry,
    IdentityScheme,
    IdentitySchemeRegistry,
)
from p2p.discv5.constants import (
    MAX_ENR_SIZE,
    ENR_REPR_PREFIX,
    IP_V4_SIZE,
    IP_V6_SIZE,
)


class ENRContentSedes:

    @classmethod
    def serialize(cls, enr: "BaseENR") -> Tuple[bytes, ...]:
        serialized_sequence_number = big_endian_int.serialize(enr.sequence_number)

        sorted_key_value_pairs = sorted(enr.items(), key=operator.itemgetter(0))

        serialized_keys = tuple(binary.serialize(key) for key, _ in sorted_key_value_pairs)
        values_and_serializers = tuple(
            (value, ENR_KEY_SEDES_MAPPING.get(key, FALLBACK_ENR_VALUE_SEDES))
            for key, value in sorted_key_value_pairs
        )
        serialized_values = tuple(
            value_serializer.serialize(value)
            for value, value_serializer in values_and_serializers
        )
        return tuple(cons(
            serialized_sequence_number,
            interleave((
                serialized_keys,
                serialized_values,
            ))
        ))

    @classmethod
    def deserialize(cls,
                    serialized_enr: Sequence[bytes],
                    identity_scheme_registry: IdentitySchemeRegistry = default_id_scheme_registry,
                    ) -> "UnsignedENR":
        cls._validate_serialized_length(serialized_enr)
        sequence_number = big_endian_int.deserialize(serialized_enr[0])
        kv_pairs = cls._deserialize_kv_pairs(serialized_enr)
        return UnsignedENR(sequence_number, kv_pairs, identity_scheme_registry)

    @classmethod
    @to_dict
    def _deserialize_kv_pairs(cls, serialized_enr: Sequence[bytes]) -> Iterable[Tuple[bytes, Any]]:
        serialized_keys = serialized_enr[1::2]
        serialized_values = serialized_enr[2::2]

        keys = tuple(binary.deserialize(serialized_key) for serialized_key in serialized_keys)
        cls._validate_key_uniqueness(keys, serialized_enr)
        cls._validate_key_order(keys, serialized_enr)

        value_deserializers = tuple(
            ENR_KEY_SEDES_MAPPING.get(key, FALLBACK_ENR_VALUE_SEDES)
            for key in keys
        )
        values = tuple(
            value_deserializer.deserialize(serialized_value)
            for value_deserializer, serialized_value in zip(value_deserializers, serialized_values)
        )

        return dict(zip(keys, values))

    @classmethod
    def _validate_serialized_length(cls, serialized_enr: Sequence[bytes]) -> None:
        if len(serialized_enr) < 1:
            raise DeserializationError(
                "ENR content must consist of at least a sequence number",
                serialized_enr,
            )
        num_keys_and_values = len(serialized_enr) - 1
        if num_keys_and_values % 2 != 0:
            raise DeserializationError(
                "ENR must have exactly one value for each key",
                serialized_enr,
            )

    @classmethod
    def _validate_key_uniqueness(cls,
                                 keys: Sequence[bytes],
                                 serialized_enr: Sequence[bytes]) -> None:
        duplicates = {key for key, num in collections.Counter(keys).items() if num > 1}
        if duplicates:
            raise DeserializationError(
                f"ENR contains the following duplicate keys: {b', '.join(duplicates).decode()}",
                serialized_enr,
            )

    @classmethod
    def _validate_key_order(cls, keys: Sequence[bytes], serialized_enr: Sequence[bytes]) -> None:
        if keys != tuple(sorted(keys)):
            raise DeserializationError(
                f"ENR keys are not sorted: {b', '.join(keys).decode()}",
                serialized_enr,
            )


class ENRSedes:

    @classmethod
    def serialize(cls, enr: "ENR") -> Tuple[bytes, ...]:
        serialized_signature = binary.serialize(enr.signature)
        serialized_content = ENRContentSedes.serialize(enr)
        return (serialized_signature,) + serialized_content

    @classmethod
    def deserialize(cls,
                    serialized_enr: Sequence[bytes],
                    identity_scheme_registry: IdentitySchemeRegistry = default_id_scheme_registry,
                    ) -> "ENR":
        cls._validate_serialized_length(serialized_enr)
        signature = binary.deserialize(serialized_enr[0])
        unsigned_enr = ENRContentSedes.deserialize(
            serialized_enr[1:],
            identity_scheme_registry=identity_scheme_registry,
        )
        return ENR(
            unsigned_enr.sequence_number,
            dict(unsigned_enr),
            signature,
            identity_scheme_registry,
        )

    @classmethod
    def _validate_serialized_length(cls, serialized_enr: Sequence[bytes]) -> None:
        if len(serialized_enr) < 2:
            raise DeserializationError(
                "ENR must contain at least a signature and a sequence number",
                serialized_enr,
            )

        num_keys_and_values = len(serialized_enr) - 2
        if num_keys_and_values % 2 != 0:
            raise DeserializationError(
                "ENR must have exactly one value for each key",
                serialized_enr,
            )

        byte_size = sum(len(element) for element in serialized_enr)
        if byte_size > MAX_ENR_SIZE:
            raise DeserializationError(
                f"ENRs must not be larger than {MAX_ENR_SIZE} bytes",
                serialized_enr,
            )


class BaseENR(Mapping[bytes, Any], ABC):
    def __init__(self,
                 sequence_number: int,
                 kv_pairs: Mapping[bytes, Any],
                 identity_scheme_registry: IdentitySchemeRegistry = default_id_scheme_registry,
                 ) -> None:
        self._sequence_number = sequence_number
        self._kv_pairs = dict(kv_pairs)
        self._identity_scheme = self._pick_identity_scheme(identity_scheme_registry)

        self._validate_sequence_number()

    def _validate_sequence_number(self) -> None:
        if self.sequence_number < 0:
            raise ValidationError("Sequence number is negative")

    def _pick_identity_scheme(self,
                              identity_scheme_registry: IdentitySchemeRegistry,
                              ) -> Type[IdentityScheme]:
        try:
            identity_scheme_id = self[IDENTITY_SCHEME_ENR_KEY]
        except KeyError:
            raise ValidationError("ENR does not specify identity scheme")

        try:
            return identity_scheme_registry[identity_scheme_id]
        except KeyError:
            raise ValidationError(f"ENR uses unsupported identity scheme {identity_scheme_id}")

    @property
    def identity_scheme(self) -> Type[IdentityScheme]:
        return self._identity_scheme

    @property
    def sequence_number(self) -> int:
        return self._sequence_number

    def get_signing_message(self) -> bytes:
        return rlp.encode(self, ENRContentSedes)

    #
    # Mapping interface
    #
    def __getitem__(self, key: bytes) -> Any:
        return self._kv_pairs[key]

    def __iter__(self) -> Iterator[bytes]:
        return iter(self._kv_pairs)

    def __len__(self) -> int:
        return len(self._kv_pairs)

    def __contains__(self, key: Any) -> bool:
        return key in self._kv_pairs

    def keys(self) -> AbstractSet[bytes]:
        return self._kv_pairs.keys()

    def values(self) -> ValuesView[Any]:
        return self._kv_pairs.values()

    def items(self) -> AbstractSet[Tuple[bytes, Any]]:
        return self._kv_pairs.items()

    def get(self, key: bytes, default: Any = None) -> Any:
        return self._kv_pairs.get(key, default)

    @abstractmethod
    def __eq__(self, other: Any) -> bool:
        pass

    @abstractmethod
    def __hash__(self) -> int:
        pass


class UnsignedENR(BaseENR, ENRContentSedes):

    def to_signed_enr(self, private_key: bytes) -> "ENR":
        signature = self.identity_scheme.create_signature(self, private_key)

        transient_identity_scheme_registry = IdentitySchemeRegistry()
        transient_identity_scheme_registry.register(self.identity_scheme)

        return ENR(
            self.sequence_number,
            dict(self),
            signature,
            identity_scheme_registry=transient_identity_scheme_registry,
        )

    def __eq__(self, other: Any) -> bool:
        return other.__class__ is self.__class__ and dict(other) == dict(self)

    def __hash__(self) -> int:
        return hash((
            self.sequence_number,
            tuple(self.items()),
        ))


class ENR(BaseENR, ENRSedes):
    def __init__(self,
                 sequence_number: int,
                 kv_pairs: Mapping[bytes, Any],
                 signature: bytes,
                 identity_scheme_registry: IdentitySchemeRegistry = default_id_scheme_registry,
                 ) -> None:
        self._signature = signature
        super().__init__(sequence_number, kv_pairs, identity_scheme_registry)

    @classmethod
    def from_repr(cls,
                  representation: str,
                  identity_scheme_registry: IdentitySchemeRegistry = default_id_scheme_registry,
                  ) -> "ENR":
        if not representation.startswith("enr:"):
            raise ValidationError(f"Invalid ENR representation: {representation}")

        unpadded_b64 = representation[4:]
        padded_b64 = unpadded_b64 + "=" * (4 - len(unpadded_b64) % 4)
        rlp_encoded = base64.urlsafe_b64decode(padded_b64)
        return rlp.decode(rlp_encoded, cls, identity_scheme_registry=identity_scheme_registry)

    @property
    def signature(self) -> bytes:
        return self._signature

    def validate_signature(self) -> None:
        self.identity_scheme.validate_signature(self)

    def extract_node_address(self) -> bytes:
        return self.identity_scheme.extract_node_address(self)

    def __eq__(self, other: Any) -> bool:
        return (
            other.__class__ is self.__class__ and
            other.sequence_number == self.sequence_number and
            dict(other) == dict(self) and
            other.signature == self.signature
        )

    def __hash__(self) -> int:
        return hash((
            self.signature,
            self.sequence_number,
            tuple(self.items()),
        ))

    def __repr__(self) -> str:
        base64_rlp = base64.urlsafe_b64encode(rlp.encode(self))
        unpadded_base64_rlp = base64_rlp.rstrip(b"=")
        return "".join((
            ENR_REPR_PREFIX,
            unpadded_base64_rlp.decode("ASCII"),
        ))


IDENTITY_SCHEME_ENR_KEY = b"id"

ENR_KEY_SEDES_MAPPING = {
    b"id": binary,
    b"secp256k1": Binary.fixed_length(33),
    b"ip": Binary.fixed_length(IP_V4_SIZE),
    b"tcp": big_endian_int,
    b"udp": big_endian_int,
    b"ip6": Binary.fixed_length(IP_V6_SIZE),
    b"tcp6": big_endian_int,
    b"udp6": big_endian_int,
}

# Use the binary sedes for values with an unknown key in an ENR as it is valid for all inputs and
# conveys the least amount of interpretation of the data.
FALLBACK_ENR_VALUE_SEDES = binary
