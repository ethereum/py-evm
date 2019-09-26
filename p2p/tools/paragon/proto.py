import logging

from p2p.protocol import BaseProtocol

from .commands import (
    BroadcastData,
    GetSum,
    Sum,
)


class ParagonProtocol(BaseProtocol):
    name = 'paragon'
    version = 1
    commands = (
        BroadcastData,
        GetSum, Sum,
    )
    command_length = 3
    logger = logging.getLogger("p2p.tools.paragon.proto.ParagonProtocol")
