import asyncio
import pytest
import socket

from eth_keys import keys

from evm.chains.ropsten import RopstenChain, ROPSTEN_GENESIS_HEADER
from evm.db.chain import ChainDB
from evm.db.header import HeaderDB
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


def get_server(privkey, address, peer_class):
    base_db = MemoryDB()
    headerdb = HeaderDB(base_db)
    chaindb = ChainDB(base_db)
    chaindb.persist_header(ROPSTEN_GENESIS_HEADER)
    chain = RopstenChain(base_db)
    server = Server(
        privkey,
        address,
        chain,
        chaindb,
        headerdb,
        base_db,
        network_id=1,
        min_peers=1,
        peer_class=peer_class,
    )
    return server


@pytest.fixture
async def server():
    server = get_server(RECEIVER_PRIVKEY, SERVER_ADDRESS, ETHPeer)
    await asyncio.wait_for(server._start(), timeout=1)
    yield server
    server.cancel_token.trigger()
    await asyncio.wait_for(server._close(), timeout=1)


@pytest.fixture
async def receiver_server_with_dumb_peer():
    server = get_server(RECEIVER_PRIVKEY, SERVER_ADDRESS, DumbPeer)
    await asyncio.wait_for(server._start(), timeout=1)
    yield server
    server.cancel_token.trigger()
    await asyncio.wait_for(server._close(), timeout=1)


@pytest.fixture
async def initiator_server_with_dumb_peer():
    server = get_server(INITIATOR_PRIVKEY, INITIATOR_ADDRESS, DumbPeer)
    await asyncio.wait_for(server._start(), timeout=1)
    yield server
    server.cancel_token.trigger()
    await asyncio.wait_for(server._close(), timeout=1)


@pytest.mark.asyncio
async def test_server_authenticates_incoming_connections(monkeypatch, server, event_loop):
    async def mock_do_handshake(self):
        pass

    # Only test the authentication in this test.
    monkeypatch.setattr(ETHPeer, 'do_p2p_handshake', mock_do_handshake)
    monkeypatch.setattr(ETHPeer, 'do_sub_proto_handshake', mock_do_handshake)

    # Send auth init message to the server.
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(SERVER_ADDRESS.ip, SERVER_ADDRESS.tcp_port),
        timeout=1)
    writer.write(eip8_values['auth_init_ciphertext'])
    await asyncio.wait_for(writer.drain(), timeout=1)

    # Await the server replying auth ack.
    await asyncio.wait_for(
        reader.read(len(eip8_values['auth_ack_ciphertext'])),
        timeout=1)

    # The sole connected node is our initiator.
    assert len(server.peer_pool.connected_nodes) == 1
    initiator_peer = server.peer_pool.connected_nodes[INITIATOR_REMOTE]
    assert isinstance(initiator_peer, ETHPeer)
    assert initiator_peer.privkey == RECEIVER_PRIVKEY

    # Stop our peer to make sure its pending asyncio tasks are cancelled.
    await initiator_peer.cancel()


@pytest.mark.asyncio
async def test_two_servers(event_loop,
                           receiver_server_with_dumb_peer,
                           initiator_server_with_dumb_peer):
    nodes = [RECEIVER_REMOTE]
    await initiator_server_with_dumb_peer.peer_pool._connect_to_nodes(nodes)
    # Give the receiver_server a chance to ack the handshake.
    await asyncio.sleep(0.1)

    assert len(receiver_server_with_dumb_peer.peer_pool.connected_nodes) == 1
    assert len(initiator_server_with_dumb_peer.peer_pool.connected_nodes) == 1

    # Stop our peer to make sure its pending asyncio tasks are cancelled.
    peer = list(receiver_server_with_dumb_peer.peer_pool.connected_nodes.values())[0]
    await peer.cancel()
