import asyncio
import pytest
import socket

from eth_keys import keys

from evm.db.chain import ChainDB
from evm.db.backends.memory import MemoryDB
from p2p.kademlia import (
    Node,
    Address,
)
from p2p.peer import (
    ETHPeer,
    PeerPool,
)
from p2p.server import Server

from auth_constants import eip8_values


def get_open_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port


SERVER_ADDRESS = Address('127.0.0.1', get_open_port())
INITIATOR_PUBKEY = keys.PrivateKey(eip8_values['initiator_private_key']).public_key
INITIATOR_ADDRESS = Address('127.0.0.1', get_open_port() + 1)
INITIATOR_REMOTE = Node(INITIATOR_PUBKEY, INITIATOR_ADDRESS)


@pytest.fixture
def server():
    privkey = keys.PrivateKey(eip8_values['receiver_private_key'])
    chaindb = ChainDB(MemoryDB())
    server = Server(privkey, SERVER_ADDRESS, chaindb, [], 1)
    return server


def test_server_authenticates_incoming_connections(server, event_loop):
    # Start server.
    asyncio.set_event_loop(event_loop)
    asyncio.ensure_future(server.run())
    # Send ping from client
    event_loop.run_until_complete(ping_server())
    event_loop.run_until_complete(stall(1))
    # Assert server still running
    assert isinstance(server.peer_pool, PeerPool)
    assert server.cancel_token.triggered is False
    assert server.peer_pool.cancel_token.triggered is False
    # The sole connected node is our initiator
    assert len(server.peer_pool.connected_nodes) is 1
    initiator_peer = server.peer_pool.connected_nodes[INITIATOR_REMOTE]
    assert isinstance(initiator_peer, ETHPeer)
    assert initiator_peer.remote == INITIATOR_REMOTE
    assert initiator_peer.privkey == keys.PrivateKey(eip8_values['receiver_private_key'])
    # Stop server
    asyncio.ensure_future(server.stop())
    event_loop.run_until_complete(stall(1))
    assert server.cancel_token.triggered is True
    assert server.peer_pool.cancel_token.triggered is True


async def ping_server():
    await stall(1)
    asyncio.ensure_future(send_auth_msg_to_server(
        SERVER_ADDRESS, eip8_values['auth_init_ciphertext'])
    )


async def stall(t):
    await asyncio.sleep(t)


async def send_auth_msg_to_server(address, messages):
    reader, writer = await asyncio.open_connection(address.ip, address.udp_port)
    writer.write(messages)
    if writer.can_write_eof():
        writer.write_eof()
    await writer.drain()
