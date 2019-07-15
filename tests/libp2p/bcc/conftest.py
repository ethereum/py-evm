import asyncio

import pytest

from p2p.ecies import (
    generate_privkey,
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


@pytest.fixture
def num_nodes():
    return 3


@pytest.fixture
async def nodes(event_loop, num_nodes, unused_tcp_port_factory):
    _nodes = tuple(
        Node(
            privkey=generate_privkey(),
            listen_ip="127.0.0.1",
            listen_port=unused_tcp_port_factory(),
            security_protocol_ops={SECURITY_PROTOCOL_ID: InsecureTransport("plaintext")},
            muxer_protocol_ids=[MULTIPLEXING_PROTOCOL_ID],
            gossipsub_params=None,
        )
        for _ in range(num_nodes)
    )
    for n in _nodes:
        asyncio.ensure_future(n.run())
        await n.events.started.wait()
    yield _nodes
    for n in _nodes:
        await n.close()
        await n.cancel()
