from typing import (
    Type,
    TYPE_CHECKING,
)
from collections import (
    UserDict,
)

import rlp
from rlp.sedes import (
    big_endian_int,
    binary,
    boolean,
    Binary,
    CountableList,
)

from eth_utils import (
    int_to_big_endian,
)

from p2p.discv5.enr import (
    ENR,
)
from p2p.discv5.constants import (
    TOPIC_HASH_SIZE,
    IP_V4_SIZE,
    IP_V6_SIZE,
)


# https://github.com/python/mypy/issues/5264#issuecomment-399407428
if TYPE_CHECKING:
    MessageTypeRegistryBaseType = UserDict[int, Type["BaseMessage"]]
else:
    MessageTypeRegistryBaseType = UserDict


#
# Custom sedes objects
#
topic_sedes = Binary.fixed_length(TOPIC_HASH_SIZE)


class IPAddressSedes(Binary):

    def __init__(self) -> None:
        super().__init__()

    def is_valid_length(self, length: int) -> bool:
        return length in (IP_V4_SIZE, IP_V6_SIZE)


ip_address_sedes = IPAddressSedes()


class MessageTypeRegistry(MessageTypeRegistryBaseType):

    def register(self,
                 message_data_class: Type["BaseMessage"]
                 ) -> Type["BaseMessage"]:
        """Class Decorator to register BaseMessage classes."""
        message_type = message_data_class.message_type
        if message_type is None:
            raise ValueError("Message type must be defined")

        if message_type in self:
            raise ValueError(f"Message with type {message_type} is already defined")

        if not self:
            expected_message_type = 1
        else:
            expected_message_type = max(self.keys()) + 1

        if not message_type == expected_message_type:
            raise ValueError(
                f"Expected message type {expected_message_type}, but got {message_type}",
            )

        self[message_type] = message_data_class

        return message_data_class


default_message_type_registry = MessageTypeRegistry()


#
# Message types
#
class BaseMessage(rlp.Serializable):
    message_type: int

    def to_bytes(self) -> bytes:
        return b"".join((
            int_to_big_endian(self.message_type),
            rlp.encode(self),
        ))


@default_message_type_registry.register
class PingMessage(BaseMessage):
    message_type = 1

    fields = (
        ("request_id", big_endian_int),
        ("enr_seq", big_endian_int),
    )


@default_message_type_registry.register
class PongMessage(BaseMessage):
    message_type = 2

    fields = (
        ("request_id", big_endian_int),
        ("enr_seq", big_endian_int),
        ("packet_ip", ip_address_sedes),
        ("packet_port", big_endian_int),
    )


@default_message_type_registry.register
class FindNodeMessage(BaseMessage):
    message_type = 3

    fields = (
        ("request_id", big_endian_int),
        ("distance", big_endian_int),
    )


@default_message_type_registry.register
class NodesMessage(BaseMessage):
    message_type = 4

    fields = (
        ("request_id", big_endian_int),
        ("total", big_endian_int),
        ("enrs", CountableList(ENR)),
    )


@default_message_type_registry.register
class ReqTicketMessage(BaseMessage):
    message_type = 5

    fields = (
        ("request_id", big_endian_int),
        ("topic", topic_sedes),
    )


@default_message_type_registry.register
class TicketMessage(BaseMessage):
    message_type = 6

    fields = (
        ("request_id", big_endian_int),
        ("ticket", binary),
        ("wait_time", big_endian_int),
    )


@default_message_type_registry.register
class RegTopicMessage(BaseMessage):
    message_type = 7

    fields = (
        ("request_id", big_endian_int),
        ("ticket", binary),
    )


@default_message_type_registry.register
class RegConfirmationMessage(BaseMessage):
    message_type = 8

    fields = (
        ("request_id", big_endian_int),
        ("registered", boolean),
    )


@default_message_type_registry.register
class TopicQueryMessage(BaseMessage):
    message_type = 9

    fields = (
        ("request_id", big_endian_int),
        ("topic", topic_sedes),
    )
