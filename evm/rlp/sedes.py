from rlp.sedes import (
    BigEndianInt,
    Binary,
    CountableList,
)
from rlp.exceptions import (
    ListSerializationError,
    ListDeserializationError,
)


class AccessListElement(CountableList):

    def __init__(self):
        super().__init__(Binary(max_length=32))

    def serialize(self, obj):
        result = super().serialize(obj)
        if not obj:
            raise ListSerializationError(
                "Access list elements need to specify at least an address"
            )
        elif len(obj[0]) != 20:
            raise ListSerializationError(
                "Access list elements need to start with a 20 byte address (got {0} bytes)".format(
                    len(obj[0])
                )
            )
        return result

    def deserialize(self, serial):
        result = super().deserialize(serial)
        if not result:
            raise ListDeserializationError(
                "Access list elements need to specify at least an address"
            )
        elif len(result[0]) != 20:
            raise ListDeserializationError(
                "Access list elements need to start with a 20 byte address (got {0} bytes)".format(
                    len(result[0])
                )
            )
        return result


address = Binary.fixed_length(20, allow_empty=True)
hash32 = Binary.fixed_length(32)
int32 = BigEndianInt(32)
int256 = BigEndianInt(256)
trie_root = Binary.fixed_length(32, allow_empty=True)
access_list_element = AccessListElement()
access_list = CountableList(access_list_element)
