import logging

from typing import (
    Any,
    Dict,
)

from p2p.protocol import (
    Protocol,
)

from .commands import (
    BroadcastData,
    GetSum,
    Sum,
)


class ParagonProtocol(Protocol):
    name = 'paragon'
    version = 1
    _commands = (
        BroadcastData,
        GetSum, Sum,
    )
    cmd_length = 3
    logger = logging.getLogger("p2p.tools.paragon.proto.ParagonProtocol")

    #
    # Broadcast
    #
    def send_broadcast_data(self, data: bytes) -> None:
        cmd = BroadcastData(self.cmd_id_offset, self.snappy_support)
        msg: Dict[str, Any] = {'data': data}
        header, body = cmd.encode(msg)
        self.transport.send(header, body)

    #
    # Sum
    #
    def send_get_sum(self, value_a: int, value_b: int) -> None:
        cmd = GetSum(self.cmd_id_offset, self.snappy_support)
        msg: Dict[str, Any] = {'a': value_a, 'b': value_b}
        header, body = cmd.encode(msg)
        self.transport.send(header, body)

    def send_sum(self, result: int) -> None:
        cmd = GetSum(self.cmd_id_offset, self.snappy_support)
        msg: Dict[str, Any] = {'result': result}
        header, body = cmd.encode(msg)
        self.transport.send(header, body)
