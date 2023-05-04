from typing import (
    Any,
    Sequence,
    Type,
)

from cached_property import (
    cached_property,
)
from eth_bloom import (
    BloomFilter,
)
from eth_utils import (
    ValidationError,
    to_bytes,
    to_int,
)
import rlp
from rlp.sedes import (
    Binary,
)

from eth.abc import (
    DecodedZeroOrOneLayerRLP,
    LogAPI,
    ReceiptAPI,
    ReceiptBuilderAPI,
    ReceiptDecoderAPI,
)
from eth.exceptions import (
    UnrecognizedTransactionType,
)
from eth.rlp.receipts import (
    Receipt,
)

from .constants import (
    ACCESS_LIST_TRANSACTION_TYPE,
    VALID_TRANSACTION_TYPES,
)

TYPED_RECEIPT_BODY_CODECS = {
    # Note that the body of a "type 1" receipt uses exactly the same codec as a
    # legacy receipt, so we can simply reuse all the logic.
    ACCESS_LIST_TRANSACTION_TYPE: Receipt,
}


class TypedReceipt(ReceiptAPI, ReceiptDecoderAPI):
    type_id: int
    rlp_type = Binary(min_length=1)  # must have at least one byte for the type
    _inner: ReceiptAPI
    codecs = TYPED_RECEIPT_BODY_CODECS

    def __init__(self, type_id: int, proxy_target: ReceiptAPI) -> None:
        self.type_id = type_id
        self._inner = proxy_target

        # Doing validation here means we don't have to validate on every encode()
        payload_codec = self.get_payload_codec(type_id)
        if not isinstance(proxy_target, payload_codec):
            raise ValidationError(
                f"Cannot embed target {proxy_target!r} "
                f"which doesn't match type ID {type_id}"
            )

    @classmethod
    def decode(cls, encoded: bytes) -> ReceiptAPI:
        type_id = to_int(encoded[0])
        payload = encoded[1:]

        payload_codec = cls.get_payload_codec(type_id)
        inner_receipt = payload_codec.decode(payload)
        return cls(type_id, inner_receipt)

    def encode(self) -> bytes:
        return self._type_byte + self._inner.encode()

    @classmethod
    def get_payload_codec(cls, type_id: int) -> Type[ReceiptDecoderAPI]:
        if type_id in cls.codecs:
            return cls.codecs[type_id]
        elif type_id in VALID_TRANSACTION_TYPES:
            raise UnrecognizedTransactionType(type_id, "Unknown receipt type")
        else:
            raise ValidationError(
                f"Cannot build typed receipt with {hex(type_id)} >= 0x80"
            )

    @classmethod
    def deserialize(cls, encoded_unchecked: DecodedZeroOrOneLayerRLP) -> ReceiptAPI:
        # binary checks a few basics, like the length of the bytes
        encoded = cls.rlp_type.deserialize(encoded_unchecked)
        return cls.decode(encoded)

    @classmethod
    def serialize(cls, obj: "TypedReceipt") -> DecodedZeroOrOneLayerRLP:
        encoded = obj.encode()
        return cls.rlp_type.serialize(encoded)

    @cached_property
    def _type_byte(self) -> bytes:
        return to_bytes(self.type_id)

    @property
    def state_root(self) -> bytes:
        return self._inner.state_root

    @property
    def gas_used(self) -> int:
        return self._inner.gas_used

    @property
    def bloom(self) -> int:
        return self._inner.bloom

    @property
    def logs(self) -> Sequence[LogAPI]:
        return self._inner.logs

    @property
    def bloom_filter(self) -> BloomFilter:
        return self._inner.bloom_filter

    def copy(self, *args: Any, **kwargs: Any) -> ReceiptAPI:
        inner_copy = self._inner.copy(*args, **kwargs)
        return type(self)(self.type_id, inner_copy)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, TypedReceipt):
            return False
        else:
            return self.type_id == other.type_id and self._inner == other._inner


class BerlinReceiptBuilder(ReceiptBuilderAPI):
    legacy_sedes = Receipt
    typed_receipt_class = TypedReceipt

    @classmethod
    def decode(cls, encoded: bytes) -> ReceiptAPI:
        if len(encoded) == 0:
            raise ValidationError("Encoded receipt was empty, which makes it invalid")

        type_id = to_int(encoded[0])
        if type_id in cls.typed_receipt_class.codecs:
            return cls.typed_receipt_class.decode(encoded)
        else:
            return rlp.decode(encoded, sedes=cls.legacy_sedes)

    @classmethod
    def deserialize(cls, encoded: DecodedZeroOrOneLayerRLP) -> ReceiptAPI:
        if isinstance(encoded, bytes):
            return cls.typed_receipt_class.deserialize(encoded)
        else:
            return cls.legacy_sedes.deserialize(encoded)

    @classmethod
    def serialize(cls, obj: ReceiptAPI) -> DecodedZeroOrOneLayerRLP:
        return cls.legacy_sedes.serialize(obj)
