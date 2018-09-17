from p2p.peer import (
    BasePeer,
    BasePeerContext,
    BasePeerPool,
    BasePeerFactory,
)
from p2p.protocol import (
    Command,
    _DecodedMsgType,
)

from .proto import ParagonProtocol


class ParagonPeer(BasePeer):
    _supported_sub_protocols = [ParagonProtocol]
    sub_proto: ParagonProtocol = None

    async def send_sub_proto_handshake(self) -> None:
        pass

    async def process_sub_proto_handshake(
            self, cmd: Command, msg: _DecodedMsgType) -> None:
        pass

    async def do_sub_proto_handshake(self) -> None:
        pass


class ParagonContext(BasePeerContext):
    # nothing magic here.  Simply an example of how the context class can be
    # used to store data specific to a certain peer class.
    paragon: str = "paragon"


class ParagonPeerFactory(BasePeerFactory):
    peer_class = ParagonPeer
    context: ParagonContext


class ParagonPeerPool(BasePeerPool):
    peer_factory_class = ParagonPeerFactory
    context: ParagonContext
