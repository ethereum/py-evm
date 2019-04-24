import asyncio

import pytest

from p2p.exceptions import NoMatchingPeerCapabilities
from p2p.p2p_proto import DisconnectReason, P2PProtocol

from trinity.protocol.eth.peer import ETHPeer
from trinity.protocol.eth.proto import ETHProtocol
from trinity.protocol.les.peer import LESPeer
from trinity.protocol.les.proto import (
    LESProtocol,
    LESProtocolV2,
)

from tests.core.peer_helpers import (
    get_directly_linked_peers_without_handshake,
    get_directly_linked_peers,
    MockPeerPoolWithConnectedPeers,
)


@pytest.mark.parametrize(
    'peer_class,proto',
    (
        (LESPeer, LESProtocolV2),
        (ETHPeer, ETHProtocol),
    )
)
@pytest.mark.asyncio
async def test_directly_linked_peers(request, event_loop, peer_class, proto):
    peer1, _ = await get_directly_linked_peers(request, event_loop, alice_peer_class=peer_class)
    assert isinstance(peer1.sub_proto, proto)


@pytest.mark.asyncio
async def test_les_handshake():
    peer1, peer2 = await get_directly_linked_peers_without_handshake(alice_peer_class=LESPeer)

    # Perform the base protocol (P2P) handshake.
    await asyncio.gather(peer1.do_p2p_handshake(), peer2.do_p2p_handshake())
    # Perform the handshake for the enabled sub-protocol (LES).
    await asyncio.gather(peer1.do_sub_proto_handshake(), peer2.do_sub_proto_handshake())

    assert isinstance(peer1.sub_proto, LESProtocol)
    assert isinstance(peer2.sub_proto, LESProtocol)


@pytest.mark.parametrize(
    'snappy_support',
    (
        True,
        False,
    )
)
def test_sub_protocol_selection(snappy_support):
    peer = ProtoMatchingPeer([LESProtocol, LESProtocolV2], snappy_support)

    proto = peer.select_sub_protocol([
        (LESProtocol.name, LESProtocol.version),
        (LESProtocolV2.name, LESProtocolV2.version),
        (LESProtocolV3.name, LESProtocolV3.version),
        ('unknown', 1),
    ],
        snappy_support=snappy_support
    )

    assert isinstance(proto, LESProtocolV2)
    assert proto.cmd_id_offset == peer.base_protocol.cmd_length

    with pytest.raises(NoMatchingPeerCapabilities):
        peer.select_sub_protocol([('unknown', 1)], snappy_support)


@pytest.mark.asyncio
async def test_peer_pool_iter(request, event_loop):
    peer1, _ = await get_directly_linked_peers(request, event_loop)
    peer2, _ = await get_directly_linked_peers(request, event_loop)
    peer3, _ = await get_directly_linked_peers(request, event_loop)
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


class LESProtocolV3(LESProtocol):
    version = 3


class ProtoMatchingPeer(LESPeer):

    def __init__(self, supported_sub_protocols, snappy_support):
        self.supported_sub_protocols = supported_sub_protocols
        self.base_protocol = P2PProtocol(self, snappy_support)
