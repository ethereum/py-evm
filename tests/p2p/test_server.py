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


port = get_open_port()
SERVER_ADDRESS = Address('127.0.0.1', udp_port=port, tcp_port=port)
INITIATOR_PUBKEY = keys.PrivateKey(eip8_values['initiator_private_key']).public_key
INITIATOR_ADDRESS = Address('127.0.0.1', get_open_port() + 1)
INITIATOR_REMOTE = Node(INITIATOR_PUBKEY, INITIATOR_ADDRESS)


@pytest.fixture
def server():
    privkey = keys.PrivateKey(eip8_values['receiver_private_key'])
    chaindb = ChainDB(MemoryDB())
    server = Server(privkey, SERVER_ADDRESS, chaindb, [], 1)
    return server


# FIXME: Instead of starting an actual server and send data over the wire, this test should create
# StreamReaders and StreamWriters and connect them directly, like in test_auth.py. That way we
# don't need those "strategically" placed sleep() calls.
@pytest.mark.asyncio
async def test_server_authenticates_incoming_connections(server, event_loop):
    await server.start()
    await send_auth_msg_to_server(SERVER_ADDRESS, eip8_values['auth_init_ciphertext'])
    # Yield control just so that the server has a chance to process the auth msg and respond to
    # the remote.
    await asyncio.sleep(0.2)

    # TODO: Assert that the server sent the expected ACK msg to the remote and that the remote
    # hasn't disconnected after processing that msg.

    # The sole connected node is our initiator
    assert len(server.peer_pool.connected_nodes) == 1
    initiator_peer = server.peer_pool.connected_nodes[INITIATOR_REMOTE]
    assert isinstance(initiator_peer, ETHPeer)
    assert initiator_peer.privkey == keys.PrivateKey(eip8_values['receiver_private_key'])

    server._server.close()
    await server._server.wait_closed()


async def send_auth_msg_to_server(address, messages):
    reader, writer = await asyncio.open_connection(address.ip, address.udp_port)
    writer.write(messages)
    await writer.drain()
