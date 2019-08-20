from typing import (
    Iterable,
    Tuple,
)

from p2p.abc import MultiplexerAPI
from p2p.handshake import (
    Handshaker,
    HandshakeReceipt,
)

from p2p.abc import ProtocolAPI
from p2p.constants import DEVP2P_V5
from p2p.peer import (
    BasePeer,
    BasePeerContext,
    BasePeerFactory,
)
from p2p.peer_pool import BasePeerPool

from .proto import ParagonProtocol


class ParagonPeer(BasePeer):
    supported_sub_protocols = (ParagonProtocol,)
    sub_proto: ParagonProtocol = None


class ParagonContext(BasePeerContext):
    # nothing magic here.  Simply an example of how the context class can be
    # used to store data specific to a certain peer class.
    paragon: str = "paragon"

    def __init__(self,
                 client_version_string: str = 'paragon-test',
                 listen_port: int = 30303,
                 p2p_version: int = DEVP2P_V5) -> None:
        super().__init__(client_version_string, listen_port, p2p_version)


class ParagonHandshaker(Handshaker):
    protocol_class = ParagonProtocol

    async def do_handshake(self,
                           multiplexer: MultiplexerAPI,
                           protocol: ProtocolAPI) -> HandshakeReceipt:
        return HandshakeReceipt(protocol)


class ParagonPeerFactory(BasePeerFactory):
    peer_class = ParagonPeer
    context: ParagonContext

    async def get_handshakers(self) -> Tuple[Handshaker, ...]:
        return (ParagonHandshaker(),)


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
