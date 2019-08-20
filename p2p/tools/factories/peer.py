import asyncio
from typing import cast, AsyncContextManager, AsyncIterator, Tuple, Type

from async_generator import asynccontextmanager

from lahja import EndpointAPI

from cancel_token import CancelToken

from eth_keys import keys

from p2p.abc import NodeAPI
from p2p.peer import BasePeer, BasePeerContext, BasePeerFactory
from p2p.service import run_service

from p2p.tools.paragon import ParagonPeer, ParagonContext, ParagonPeerFactory

from .cancel_token import CancelTokenFactory
from .transport import MemoryTransportPairFactory


@asynccontextmanager
async def PeerPairFactory(*,
                          alice_peer_context: BasePeerContext,
                          alice_peer_factory_class: Type[BasePeerFactory],
                          bob_peer_context: BasePeerContext,
                          bob_peer_factory_class: Type[BasePeerFactory],
                          alice_remote: NodeAPI = None,
                          alice_private_key: keys.PrivateKey = None,
                          alice_client_version: str = 'alice',
                          alice_p2p_version: int = 5,
                          bob_remote: NodeAPI = None,
                          bob_private_key: keys.PrivateKey = None,
                          bob_client_version: str = 'bob',
                          bob_p2p_version: int = 5,
                          cancel_token: CancelToken = None,
                          event_bus: EndpointAPI = None,
                          ) -> AsyncIterator[Tuple[BasePeer, BasePeer]]:
    if cancel_token is None:
        cancel_token = CancelTokenFactory()

    alice_factory = alice_peer_factory_class(
        privkey=alice_private_key,
        context=alice_peer_context,
        token=cancel_token,
        event_bus=event_bus,
    )
    bob_factory = bob_peer_factory_class(
        privkey=bob_private_key,
        context=bob_peer_context,
        token=cancel_token,
        event_bus=event_bus,
    )

    # start: ConnectionPairFactory

    alice_transport, bob_transport = MemoryTransportPairFactory(
        alice_remote=alice_remote,
        alice_private_key=alice_private_key,
        bob_remote=bob_remote,
        bob_private_key=bob_private_key,
    )

    # end: ConnectionPairFactory

    alice = alice_factory.create_peer(transport=alice_transport, inbound=False)
    bob = bob_factory.create_peer(transport=bob_transport, inbound=True)

    async def do_handshake(peer: BasePeer) -> None:
        await peer.do_p2p_handshake()
        await peer.do_sub_proto_handshake()

    await asyncio.wait_for(asyncio.gather(
        do_handshake(alice),
        do_handshake(bob),
    ), timeout=1)

    async with run_service(alice), run_service(bob):
        yield alice, bob


def ParagonPeerPairFactory(*,
                           alice_peer_context: ParagonContext = None,
                           alice_remote: NodeAPI = None,
                           alice_private_key: keys.PrivateKey = None,
                           alice_client_version: str = 'alice',
                           bob_peer_context: ParagonContext = None,
                           bob_remote: NodeAPI = None,
                           bob_private_key: keys.PrivateKey = None,
                           bob_client_version: str = 'bob',
                           cancel_token: CancelToken = None,
                           event_bus: EndpointAPI = None,
                           ) -> AsyncContextManager[Tuple[ParagonPeer, ParagonPeer]]:
    if alice_peer_context is None:
        alice_peer_context = ParagonContext()
    if bob_peer_context is None:
        bob_peer_context = ParagonContext()

    return cast(AsyncContextManager[Tuple[ParagonPeer, ParagonPeer]], PeerPairFactory(
        alice_peer_context=alice_peer_context,
        alice_peer_factory_class=ParagonPeerFactory,
        bob_peer_context=bob_peer_context,
        bob_peer_factory_class=ParagonPeerFactory,
        alice_remote=alice_remote,
        alice_private_key=alice_private_key,
        alice_client_version=alice_client_version,
        bob_remote=bob_remote,
        bob_private_key=bob_private_key,
        bob_client_version=bob_client_version,
        cancel_token=cancel_token,
        event_bus=event_bus,
    ))
