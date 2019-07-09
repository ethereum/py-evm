import inspect

import rlp
from rlp.sedes import (
    big_endian_int,
)

from p2p.discv5 import messages
from p2p.discv5.messages import (
    default_message_type_registry,
    BaseMessage,
    PingMessage,
)


def test_default_message_registry():
    message_data_classes = tuple(
        member for _, member in inspect.getmembers(messages)
        if inspect.isclass(member) and issubclass(member, BaseMessage) and member is not BaseMessage
    )
    assert len(default_message_type_registry) == len(message_data_classes)
    for message_data_class in message_data_classes:
        message_type = message_data_class.message_type
        assert message_type in default_message_type_registry
        assert default_message_type_registry[message_type] is message_data_class


def test_all_messages_have_request_id():
    for message_data_class in default_message_type_registry.values():
        first_field_name, first_field_sedes = message_data_class._meta.fields[0]
        assert first_field_name == "request_id"
        assert first_field_sedes == big_endian_int


def test_message_types_are_continuous():
    sorted_message_types = sorted(default_message_type_registry.keys())
    assert sorted_message_types == list(range(1, len(sorted_message_types) + 1))


def test_message_encoding():
    message = PingMessage(request_id=5, enr_seq=10)
    encoded_message = message.to_bytes()
    assert encoded_message[0] == message.message_type
    assert encoded_message[1:] == rlp.encode(message)
