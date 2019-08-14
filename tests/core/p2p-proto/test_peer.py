import asyncio

import pytest

from p2p.disconnect import DisconnectReason

from trinity.protocol.eth.peer import ETHPeer
from trinity.protocol.eth.proto import ETHProtocol
from trinity.protocol.les.peer import LESPeer
from trinity.protocol.les.proto import (
    LESProtocol,
    LESProtocolV2,
)

from trinity.tools.factories import (
    ETHPeerPairFactory,
    LESV1PeerPairFactory,
    LESV2PeerPairFactory,
)

from tests.core.peer_helpers import (
    MockPeerPoolWithConnectedPeers,
)


@pytest.mark.asyncio
async def test_LES_v1_peers():
    async with LESV1PeerPairFactory() as (alice, bob):
        assert isinstance(alice, LESPeer)
        assert isinstance(bob, LESPeer)

        assert isinstance(alice.sub_proto, LESProtocol)
        assert isinstance(bob.sub_proto, LESProtocol)


@pytest.mark.asyncio
async def test_LES_v2_peers():
    async with LESV2PeerPairFactory() as (alice, bob):
        assert isinstance(alice, LESPeer)
        assert isinstance(bob, LESPeer)

        assert isinstance(alice.sub_proto, LESProtocolV2)
        assert isinstance(bob.sub_proto, LESProtocolV2)


@pytest.mark.asyncio
async def test_ETH_peers():
    async with ETHPeerPairFactory() as (alice, bob):
        assert isinstance(alice, ETHPeer)
        assert isinstance(bob, ETHPeer)

        assert isinstance(alice.sub_proto, ETHProtocol)
        assert isinstance(bob.sub_proto, ETHProtocol)


@pytest.mark.asyncio
async def test_peer_pool_iter(request, event_loop):
    factory_a = ETHPeerPairFactory()
    factory_b = ETHPeerPairFactory()
    factory_c = ETHPeerPairFactory()
    async with factory_a as (peer1, _), factory_b as (peer2, _), factory_c as (peer3, _):
        pool = MockPeerPoolWithConnectedPeers([peer1, peer2, peer3])
        peers = list([peer async for peer in pool])

        assert len(peers) == 3
        assert peer1 in peers
        assert peer2 in peers
        assert peer3 in peers

        peers = []
        asyncio.ensure_future(peer2.disconnect(DisconnectReason.disconnect_requested))
        async for peer in pool:
            peers.append(peer)

        assert len(peers) == 2
        assert peer1 in peers
        assert peer2 not in peers
        assert peer3 in peers
