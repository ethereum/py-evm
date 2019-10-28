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
from eth_utils import to_bytes

from eth_keys import keys
from eth.constants import GENESIS_DIFFICULTY, GENESIS_BLOCK_NUMBER

from p2p import kademlia
from p2p.abc import HandshakerAPI
from p2p.tools.factories import PeerPairFactory

from trinity.constants import MAINNET_NETWORK_ID

from trinity.protocol.common.context import ChainContext

from trinity.protocol.les.handshaker import LESV2Handshaker, LESV1Handshaker
from trinity.protocol.les.peer import LESPeer, LESPeerFactory
from trinity.protocol.les.proto import LESHandshakeParams, LESProtocolV1, LESProtocolV2

from trinity.tools.factories.chain_context import ChainContextFactory


MAINNET_GENESIS_HASH = to_bytes(hexstr='0xd4e56740f876aef8c010b86a40d5f56745a118d0906a34e69aec8c0db1cb8fa3')  # noqa: E501


class LESHandshakeParamsFactory(factory.Factory):
    class Meta:
        model = LESHandshakeParams

    version = LESProtocolV2.version
    network_id = MAINNET_NETWORK_ID
    head_td = GENESIS_DIFFICULTY
    head_hash = MAINNET_GENESIS_HASH
    head_number = GENESIS_BLOCK_NUMBER
    genesis_hash = MAINNET_GENESIS_HASH
    serve_headers = True
    serve_chain_since = 0
    serve_state_since = None
    serve_recent_state = None
    serve_recent_chain = None
    tx_relay = False
    flow_control_bl = None
    flow_control_mcr = None
    flow_control_mrr = None
    announce_type = factory.LazyAttribute(
        lambda o: o.version if o.version >= LESProtocolV2.version else None
    )


class LESV1HandshakerFactory(factory.Factory):
    class Meta:
        model = LESV1Handshaker

    handshake_params = factory.SubFactory(LESHandshakeParamsFactory, version=LESProtocolV1.version)


class LESV2HandshakerFactory(factory.Factory):
    class Meta:
        model = LESV2Handshaker

    handshake_params = factory.SubFactory(LESHandshakeParamsFactory, version=LESProtocolV2.version)


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
