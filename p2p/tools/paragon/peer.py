from typing import (
    Iterable,
)

from p2p.abc import CommandAPI
from p2p.peer import (
    BasePeer,
    BasePeerContext,
    BasePeerFactory,
)
from p2p.peer_pool import BasePeerPool
from p2p.typing import Payload

from .proto import ParagonProtocol


class ParagonPeer(BasePeer):
    supported_sub_protocols = (ParagonProtocol,)
    sub_proto: ParagonProtocol = None

    async def send_sub_proto_handshake(self) -> None:
        pass

    async def process_sub_proto_handshake(
            self, cmd: CommandAPI, msg: Payload) -> None:
        pass

    async def do_sub_proto_handshake(self) -> None:
        pass


class ParagonContext(BasePeerContext):
    # nothing magic here.  Simply an example of how the context class can be
    # used to store data specific to a certain peer class.
    paragon: str = "paragon"

    def __init__(self,
                 client_version_string: str = 'paragon-test',
                 listen_port: int = 30303) -> None:
        super().__init__(client_version_string, listen_port)


class ParagonPeerFactory(BasePeerFactory):
    peer_class = ParagonPeer
    context: ParagonContext


class ParagonPeerPool(BasePeerPool):
    peer_factory_class = ParagonPeerFactory
    context: ParagonContext


class ParagonMockPeerPoolWithConnectedPeers(ParagonPeerPool):
    def __init__(self, peers: Iterable[ParagonPeer]) -> None:
        super().__init__(privkey=None, context=None)
        for peer in peers:
            self.connected_nodes[peer.remote] = peer

    async def _run(self) -> None:
        raise NotImplementedError("This is a mock PeerPool implementation, you must not _run() it")
