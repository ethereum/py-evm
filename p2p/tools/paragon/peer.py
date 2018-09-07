from p2p.peer import (
    BasePeer,
)
from p2p.protocol import (
    Command,
    _DecodedMsgType,
)

from .proto import ParagonProtocol


class ParagonPeer(BasePeer):
    _supported_sub_protocols = [ParagonProtocol]
    sub_proto: ParagonProtocol = None

    async def send_sub_proto_handshake(self):
        pass

    async def process_sub_proto_handshake(
            self, cmd: Command, msg: _DecodedMsgType) -> None:
        pass

    async def do_sub_proto_handshake(self):
        pass
