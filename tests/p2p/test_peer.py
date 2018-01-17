import asyncio

import pytest

from p2p.les import (
    LESProtocol,
    LESProtocolV2,
)
from p2p.exceptions import NoMatchingPeerCapabilities
from p2p.peer import LESPeer
from p2p.p2p_proto import P2PProtocol

from peer_helpers import (
    get_directly_linked_peers_without_handshake,
    get_directly_linked_peers,
)


@pytest.mark.asyncio
async def test_directly_linked_peers(request, event_loop):
    peer1, _ = await get_directly_linked_peers(request, event_loop)
    assert isinstance(peer1.sub_proto, LESProtocolV2)


@pytest.mark.asyncio
async def test_les_handshake():
    peer1, peer2 = await get_directly_linked_peers_without_handshake()

    # Perform the base protocol (P2P) handshake.
    await asyncio.gather(peer1.do_p2p_handshake(), peer2.do_p2p_handshake())
    # Perform the handshake for the enabled sub-protocol (LES).
    await asyncio.gather(peer1.do_sub_proto_handshake(), peer2.do_sub_proto_handshake())

    assert isinstance(peer1.sub_proto, LESProtocol)
    assert isinstance(peer2.sub_proto, LESProtocol)


def test_sub_protocol_selection():
    peer = ProtoMatchingPeer([LESProtocol, LESProtocolV2])

    proto = peer.select_sub_protocol([
        (LESProtocol.name, LESProtocol.version),
        (LESProtocolV2.name, LESProtocolV2.version),
        (LESProtocolV3.name, LESProtocolV3.version),
        ('unknown', 1),
    ])

    assert isinstance(proto, LESProtocolV2)
    assert proto.cmd_id_offset == peer.base_protocol.cmd_length

    with pytest.raises(NoMatchingPeerCapabilities):
        peer.select_sub_protocol([('unknown', 1)])


class LESProtocolV3(LESProtocol):
    version = 3


class ProtoMatchingPeer(LESPeer):

    def __init__(self, supported_sub_protocols):
        self._supported_sub_protocols = supported_sub_protocols
        self.base_protocol = P2PProtocol(self)
