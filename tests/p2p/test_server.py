import asyncio
import pytest
import socket

from eth_keys import keys

from evm.db.chain import ChainDB
from evm.db.backends.memory import MemoryDB

from p2p.peer import (
    ETHPeer,
)
from p2p.kademlia import (
    Node,
    Address,
)
from p2p.server import Server

from auth_constants import eip8_values
from dumb_peer import DumbPeer


def get_open_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port


port = get_open_port()
SERVER_ADDRESS = Address('127.0.0.1', udp_port=port, tcp_port=port)
RECEIVER_PRIVKEY = keys.PrivateKey(eip8_values['receiver_private_key'])
RECEIVER_PUBKEY = RECEIVER_PRIVKEY.public_key
RECEIVER_REMOTE = Node(RECEIVER_PUBKEY, SERVER_ADDRESS)

INITIATOR_PRIVKEY = keys.PrivateKey(eip8_values['initiator_private_key'])
INITIATOR_PUBKEY = INITIATOR_PRIVKEY.public_key
INITIATOR_ADDRESS = Address('127.0.0.1', get_open_port() + 1)
INITIATOR_REMOTE = Node(INITIATOR_PUBKEY, INITIATOR_ADDRESS)


def get_server(privkey, address, bootstrap_nodes=None, peer_class=DumbPeer):
    if bootstrap_nodes is None:
        bootstrap_nodes = []
    chaindb = ChainDB(MemoryDB())
    server = Server(
        privkey,
        address,
        chaindb,
        bootstrap_nodes,
        1,
        min_peers=1,
        peer_class=peer_class,
    )
    return server


@pytest.fixture
def server():
    server = get_server(RECEIVER_PRIVKEY, SERVER_ADDRESS, bootstrap_nodes=[], peer_class=ETHPeer)
    return server


@pytest.mark.asyncio
async def test_server_authenticates_incoming_connections(monkeypatch, server, event_loop):
    async def mock_do_p2p_handshake(self):
        pass

    # Only test the authentication in this test.
    monkeypatch.setattr(ETHPeer, 'do_p2p_handshake', mock_do_p2p_handshake)

    await server.start()

    # Send auth init message to the server.
    reader, writer = await asyncio.open_connection(SERVER_ADDRESS.ip, SERVER_ADDRESS.tcp_port)
    writer.write(eip8_values['auth_init_ciphertext'])
    await writer.drain()

    # Await the server replying auth ack.
    await reader.read(len(eip8_values['auth_ack_ciphertext']))

    # The sole connected node is our initiator.
    assert len(server.peer_pool.connected_nodes) == 1
    initiator_peer = server.peer_pool.connected_nodes[INITIATOR_REMOTE]
    assert isinstance(initiator_peer, ETHPeer)
    assert initiator_peer.privkey == RECEIVER_PRIVKEY
    await server.stop()


@pytest.mark.asyncio
async def test_two_servers(event_loop):
    # Start server.
    server_1 = get_server(
        RECEIVER_PRIVKEY,
        SERVER_ADDRESS,
    )
    server_2 = get_server(
        INITIATOR_PRIVKEY,
        INITIATOR_ADDRESS,
    )

    await server_1.start()
    await server_2.start()

    nodes = [RECEIVER_REMOTE]
    await server_2.peer_pool._connect_to_nodes(nodes)

    assert len(server_1.peer_pool.connected_nodes) == 1
    assert len(server_2.peer_pool.connected_nodes) == 1

    # Stop the servers.
    await server_1.stop()
    await server_2.stop()

    # Check if they are disconnected.
    assert len(server_1.peer_pool.connected_nodes) == 0
    assert len(server_2.peer_pool.connected_nodes) == 0
