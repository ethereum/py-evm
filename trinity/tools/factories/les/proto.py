try:
    import factory
except ImportError:
    raise ImportError("The p2p.tools.factories module requires the `factory_boy` library.")

from typing import (
    cast,
    AsyncContextManager,
    Tuple,
)

from lahja import EndpointAPI

from cancel_token import CancelToken

from eth_typing import BlockNumber

from eth_keys import keys
from eth.constants import GENESIS_BLOCK_NUMBER

from p2p import kademlia
from p2p.abc import HandshakerAPI
from p2p.tools.factories import PeerPairFactory

from trinity.protocol.common.context import ChainContext

from trinity.protocol.les.handshaker import LESV2Handshaker, LESV1Handshaker
from trinity.protocol.les.peer import LESPeer, LESPeerFactory
from trinity.protocol.les.proto import LESProtocolV1, LESProtocolV2

from trinity.tools.factories.chain_context import ChainContextFactory

from .payloads import StatusPayloadFactory


class LESV1HandshakerFactory(factory.Factory):
    class Meta:
        model = LESV1Handshaker

    handshake_params = factory.SubFactory(StatusPayloadFactory, version=LESProtocolV1.version)


class LESV2HandshakerFactory(factory.Factory):
    class Meta:
        model = LESV2Handshaker

    handshake_params = factory.SubFactory(StatusPayloadFactory, version=LESProtocolV2.version)


class LESV1Peer(LESPeer):
    supported_sub_protocols = (LESProtocolV1,)  # type: ignore


class LESV1PeerFactory(LESPeerFactory):
    peer_class = LESV1Peer

    async def get_handshakers(self) -> Tuple[HandshakerAPI, ...]:
        return tuple(filter(
            # mypy doesn't know these have a `handshake_params` property
            lambda handshaker: handshaker.handshake_params.version == 1,  # type: ignore
            await super().get_handshakers()
        ))


def LESV1PeerPairFactory(*,
                         alice_peer_context: ChainContext = None,
                         alice_remote: kademlia.Node = None,
                         alice_private_key: keys.PrivateKey = None,
                         alice_client_version: str = 'alice',
                         bob_peer_context: ChainContext = None,
                         bob_remote: kademlia.Node = None,
                         bob_private_key: keys.PrivateKey = None,
                         bob_client_version: str = 'bob',
                         cancel_token: CancelToken = None,
                         event_bus: EndpointAPI = None,
                         ) -> AsyncContextManager[Tuple[LESV1Peer, LESV1Peer]]:
    if alice_peer_context is None:
        alice_peer_context = ChainContextFactory()
    if bob_peer_context is None:
        alice_genesis = alice_peer_context.headerdb.get_canonical_block_header_by_number(
            BlockNumber(GENESIS_BLOCK_NUMBER),
        )
        bob_peer_context = ChainContextFactory(
            headerdb__genesis_params={'timestamp': alice_genesis.timestamp},
        )

    return cast(AsyncContextManager[Tuple[LESV1Peer, LESV1Peer]], PeerPairFactory(
        alice_peer_context=alice_peer_context,
        alice_peer_factory_class=LESV1PeerFactory,
        bob_peer_context=bob_peer_context,
        bob_peer_factory_class=LESV1PeerFactory,
        alice_remote=alice_remote,
        alice_private_key=alice_private_key,
        alice_client_version=alice_client_version,
        bob_remote=bob_remote,
        bob_private_key=bob_private_key,
        bob_client_version=bob_client_version,
        cancel_token=cancel_token,
        event_bus=event_bus,
    ))


def LESV2PeerPairFactory(*,
                         alice_peer_context: ChainContext = None,
                         alice_remote: kademlia.Node = None,
                         alice_private_key: keys.PrivateKey = None,
                         alice_client_version: str = 'alice',
                         bob_peer_context: ChainContext = None,
                         bob_remote: kademlia.Node = None,
                         bob_private_key: keys.PrivateKey = None,
                         bob_client_version: str = 'bob',
                         cancel_token: CancelToken = None,
                         event_bus: EndpointAPI = None,
                         ) -> AsyncContextManager[Tuple[LESPeer, LESPeer]]:
    if alice_peer_context is None:
        alice_peer_context = ChainContextFactory()
    if bob_peer_context is None:
        alice_genesis = alice_peer_context.headerdb.get_canonical_block_header_by_number(
            BlockNumber(GENESIS_BLOCK_NUMBER),
        )
        bob_peer_context = ChainContextFactory(
            headerdb__genesis_params={'timestamp': alice_genesis.timestamp},
        )

    return cast(AsyncContextManager[Tuple[LESPeer, LESPeer]], PeerPairFactory(
        alice_peer_context=alice_peer_context,
        alice_peer_factory_class=LESPeerFactory,
        bob_peer_context=bob_peer_context,
        bob_peer_factory_class=LESPeerFactory,
        alice_remote=alice_remote,
        alice_private_key=alice_private_key,
        alice_client_version=alice_client_version,
        bob_remote=bob_remote,
        bob_private_key=bob_private_key,
        bob_client_version=bob_client_version,
        cancel_token=cancel_token,
        event_bus=event_bus,
    ))
