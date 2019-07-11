import pytest

from multiaddr import (
    Multiaddr,
)

from libp2p.security.insecure_security import (
    InsecureTransport,
)

from trinity.protocol.bcc_libp2p.configs import (
    SECURITY_PROTOCOL_ID,
    MULTIPLEXING_PROTOCOL_ID,
)
from trinity.protocol.bcc_libp2p.node import (
    Node,
)


@pytest.mark.asyncio
async def test_node(privkey, unused_tcp_port_factory):
    listen_maddr = Multiaddr(f"/ip4/127.0.0.1/tcp/{unused_tcp_port_factory()}")
    node = Node(
        privkey=privkey,
        listen_maddr=listen_maddr,
        security_protocol_ops={SECURITY_PROTOCOL_ID: InsecureTransport("plaintext")},
        muxer_protocol_ids=[MULTIPLEXING_PROTOCOL_ID],
        gossipsub_params=None,
    )
    await node.listen()
    assert node.host.get_addrs() == [listen_maddr.encapsulate(Multiaddr(f"/p2p/{node.peer_id}"))]
    await node.close()
