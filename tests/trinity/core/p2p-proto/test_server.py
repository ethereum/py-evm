import asyncio
import pytest
import socket

from eth_keys import keys

from cancel_token import CancelToken

from eth.chains.ropsten import RopstenChain, ROPSTEN_GENESIS_HEADER
from eth.db.chain import ChainDB
from eth.db.backends.memory import MemoryDB

from p2p.auth import HandshakeInitiator, _handshake
from p2p.peer import (
    PeerPool,
)
from p2p.kademlia import (
    Node,
    Address,
)

from trinity.protocol.eth.peer import ETHPeer
from trinity.server import Server

from tests.p2p.auth_constants import eip8_values
from tests.trinity.core.dumb_peer import DumbPeer
from tests.trinity.core.integration_test_helpers import FakeAsyncHeaderDB


def get_open_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port


port = get_open_port()
NETWORK_ID = 99
SERVER_ADDRESS = Address('127.0.0.1', udp_port=port, tcp_port=port)
RECEIVER_PRIVKEY = keys.PrivateKey(eip8_values['receiver_private_key'])
RECEIVER_PUBKEY = RECEIVER_PRIVKEY.public_key
RECEIVER_REMOTE = Node(RECEIVER_PUBKEY, SERVER_ADDRESS)

INITIATOR_PRIVKEY = keys.PrivateKey(eip8_values['initiator_private_key'])
INITIATOR_PUBKEY = INITIATOR_PRIVKEY.public_key
INITIATOR_ADDRESS = Address('127.0.0.1', get_open_port() + 1)
INITIATOR_REMOTE = Node(INITIATOR_PUBKEY, INITIATOR_ADDRESS)


class MockPeerPool:
    is_full = False
    connected_nodes = {}

    async def start_peer(self, peer):
        self.connected_nodes[peer.remote] = peer

    def is_valid_connection_candidate(self, node):
        return True

    def __len__(self):
        return len(self.connected_nodes)


def get_server(privkey, address, peer_class):
    base_db = MemoryDB()
    headerdb = FakeAsyncHeaderDB(base_db)
    chaindb = ChainDB(base_db)
    chaindb.persist_header(ROPSTEN_GENESIS_HEADER)
    chain = RopstenChain(base_db)
    server = Server(
        privkey,
        address.tcp_port,
        chain,
        chaindb,
        headerdb,
        base_db,
        network_id=NETWORK_ID,
        peer_class=peer_class,
    )
    return server


@pytest.fixture
async def server():
    server = get_server(RECEIVER_PRIVKEY, SERVER_ADDRESS, ETHPeer)
    await asyncio.wait_for(server._start_tcp_listener(), timeout=1)
    yield server
    server.cancel_token.trigger()
    await asyncio.wait_for(server._close_tcp_listener(), timeout=1)


@pytest.fixture
async def receiver_server_with_dumb_peer():
    server = get_server(RECEIVER_PRIVKEY, SERVER_ADDRESS, DumbPeer)
    await asyncio.wait_for(server._start_tcp_listener(), timeout=1)
    yield server
    server.cancel_token.trigger()
    await asyncio.wait_for(server._close_tcp_listener(), timeout=1)


@pytest.mark.asyncio
async def test_server_incoming_connection(monkeypatch, server, event_loop):
    # We need this to ensure the server can check if the peer pool is full for
    # incoming connections.
    monkeypatch.setattr(server, 'peer_pool', MockPeerPool())

    use_eip8 = False
    token = CancelToken("initiator")
    initiator = HandshakeInitiator(RECEIVER_REMOTE, INITIATOR_PRIVKEY, use_eip8, token)
    reader, writer = await initiator.connect()
    # Send auth init message to the server, then read and decode auth ack
    aes_secret, mac_secret, egress_mac, ingress_mac = await _handshake(
        initiator, reader, writer, token)

    initiator_peer = ETHPeer(
        remote=initiator.remote, privkey=initiator.privkey, reader=reader,
        writer=writer, aes_secret=aes_secret, mac_secret=mac_secret,
        egress_mac=egress_mac, ingress_mac=ingress_mac, headerdb=server.headerdb,
        network_id=NETWORK_ID)
    # Perform p2p/sub-proto handshake, completing the full handshake and causing a new peer to be
    # added to the server's pool.
    await initiator_peer.do_p2p_handshake()
    await initiator_peer.do_sub_proto_handshake()

    assert len(server.peer_pool.connected_nodes) == 1
    receiver_peer = list(server.peer_pool.connected_nodes.values())[0]
    assert isinstance(receiver_peer, ETHPeer)
    assert initiator_peer.sub_proto is not None
    assert initiator_peer.sub_proto.name == receiver_peer.sub_proto.name
    assert initiator_peer.sub_proto.version == receiver_peer.sub_proto.version
    assert receiver_peer.privkey == RECEIVER_PRIVKEY


@pytest.mark.asyncio
async def test_peer_pool_connect(monkeypatch, event_loop, receiver_server_with_dumb_peer):
    started_peers = []

    async def mock_start_peer(peer):
        nonlocal started_peers
        started_peers.append(peer)

    monkeypatch.setattr(receiver_server_with_dumb_peer, '_start_peer', mock_start_peer)
    # We need this to ensure the server can check if the peer pool is full for
    # incoming connections.
    monkeypatch.setattr(receiver_server_with_dumb_peer, 'peer_pool', MockPeerPool())

    pool = PeerPool(DumbPeer, FakeAsyncHeaderDB(MemoryDB()), NETWORK_ID, INITIATOR_PRIVKEY, tuple())
    nodes = [RECEIVER_REMOTE]
    await pool.connect_to_nodes(nodes)
    # Give the receiver_server a chance to ack the handshake.
    await asyncio.sleep(0.1)

    assert len(started_peers) == 1
    assert len(pool.connected_nodes) == 1

    # Stop our peer to make sure its pending asyncio tasks are cancelled.
    await list(pool.connected_nodes.values())[0].cancel()
