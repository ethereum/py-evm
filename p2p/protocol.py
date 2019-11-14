import logging
from typing import (
    Any,
    Sequence,
    Tuple,
    Type,
)

from eth_utils.toolz import accumulate

from p2p.abc import (
    CommandAPI,
    ProtocolAPI,
    TransportAPI,
)
from p2p.constants import P2P_PROTOCOL_COMMAND_LENGTH
from p2p.typing import Capability


class BaseProtocol(ProtocolAPI):
    logger = logging.getLogger('p2p.protocol.Protocol')

    def __init__(self,
                 transport: TransportAPI,
                 command_id_offset: int,
                 snappy_support: bool) -> None:
        self.transport = transport
        self.command_id_offset = command_id_offset
        self.snappy_support = snappy_support

        self.command_id_by_type = {
            command_type: command_id_offset + command_type.protocol_command_id
            for command_type
            in self.commands
        }
        self.command_type_by_id = {
            command_id: command_type
            for command_type, command_id
            in self.command_id_by_type.items()
        }

    def __repr__(self) -> str:
        return "(%s, %d)" % (self.name, self.version)

    @classmethod
    def supports_command(cls, command_type: Type[CommandAPI[Any]]) -> bool:
        return command_type in cls.commands

    @classmethod
    def as_capability(cls) -> Capability:
        return (cls.name, cls.version)

    def get_command_type_for_command_id(self, command_id: int) -> Type[CommandAPI[Any]]:
        return self.command_type_by_id[command_id]

    def send(self, command: CommandAPI[Any]) -> None:
        message = command.encode(self.command_id_by_type[type(command)], self.snappy_support)
        self.transport.send(message)


def get_cmd_offsets(protocol_types: Sequence[Type[ProtocolAPI]]) -> Tuple[int, ...]:
    """
    Computes the `command_id_offsets` for each protocol.  The first offset is
    always P2P_PROTOCOL_COMMAND_LENGTH since the first protocol always begins
    after the base `p2p` protocol.  Each subsequent protocol is the accumulated
    sum of all of the protocol offsets that came before it.
    """
    return tuple(accumulate(
        lambda prev_offset, protocol_class: prev_offset + protocol_class.command_length,
        protocol_types,
        P2P_PROTOCOL_COMMAND_LENGTH,
    ))[:-1]  # the `[:-1]` is to discard the last accumulated offset which is not needed
