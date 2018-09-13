import asyncio
import pytest
import socket

from eth_keys import keys

from cancel_token import CancelToken

from eth.chains.ropsten import RopstenChain, ROPSTEN_GENESIS_HEADER
from eth.db.chain import ChainDB
from eth.db.backends.memory import MemoryDB

from p2p.auth import HandshakeInitiator, _handshake
from p2p.kademlia import (
    Node,
    Address,
)
from p2p.peer import PeerConnection
from p2p.tools.paragon import (
    ParagonContext,
    ParagonPeer,
    ParagonPeerPool,
)

from trinity.server import BaseServer

from tests.p2p.auth_constants import eip8_values
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


class ParagonServer(BaseServer):
    def _make_peer_pool(self):
        return ParagonPeerPool(
            privkey=self.privkey,
            context=ParagonContext(),
            token=self.cancel_token,
        )

    def _make_syncer(self):
        return


def get_server(privkey, address):
    base_db = MemoryDB()
    headerdb = FakeAsyncHeaderDB(base_db)
    chaindb = ChainDB(base_db)
    chaindb.persist_header(ROPSTEN_GENESIS_HEADER)
    chain = RopstenChain(base_db)
    server = ParagonServer(
        privkey=privkey,
        port=address.tcp_port,
        chain=chain,
        chaindb=chaindb,
        headerdb=headerdb,
        base_db=base_db,
        network_id=NETWORK_ID,
    )
    return server


@pytest.fixture
async def server():
    server = get_server(RECEIVER_PRIVKEY, SERVER_ADDRESS)
    await asyncio.wait_for(server._start_tcp_listener(), timeout=1)
    try:
        yield server
    finally:
        server.cancel_token.trigger()
    await asyncio.wait_for(server._close_tcp_listener(), timeout=1)


@pytest.mark.asyncio
async def test_server_incoming_connection(monkeypatch, server, event_loop):
    use_eip8 = False
    token = CancelToken("initiator")
    initiator = HandshakeInitiator(RECEIVER_REMOTE, INITIATOR_PRIVKEY, use_eip8, token)
    reader, writer = await initiator.connect()
    # Send auth init message to the server, then read and decode auth ack
    aes_secret, mac_secret, egress_mac, ingress_mac = await _handshake(
        initiator, reader, writer, token)

    connection = PeerConnection(
        reader=reader,
        writer=writer,
        aes_secret=aes_secret,
        mac_secret=mac_secret,
        egress_mac=egress_mac,
        ingress_mac=ingress_mac,
    )
    initiator_peer = ParagonPeer(
        remote=initiator.remote,
        privkey=initiator.privkey,
        connection=connection,
        context=ParagonContext(),
        token=token,
    )
    # Perform p2p/sub-proto handshake, completing the full handshake and causing a new peer to be
    # added to the server's pool.
    await initiator_peer.do_p2p_handshake()
    await initiator_peer.do_sub_proto_handshake()

    # wait for peer to be processed
    while len(server.peer_pool) == 0:
        await asyncio.sleep(0)

    assert len(server.peer_pool.connected_nodes) == 1
    receiver_peer = list(server.peer_pool.connected_nodes.values())[0]
    assert isinstance(receiver_peer, ParagonPeer)
    assert initiator_peer.sub_proto is not None
    assert initiator_peer.sub_proto.name == receiver_peer.sub_proto.name
    assert initiator_peer.sub_proto.version == receiver_peer.sub_proto.version
    assert receiver_peer.privkey == RECEIVER_PRIVKEY


@pytest.mark.asyncio
async def test_peer_pool_connect(monkeypatch, event_loop, server):
    started_peers = []

    async def mock_start_peer(peer):
        nonlocal started_peers
        started_peers.append(peer)

    monkeypatch.setattr(server.peer_pool, 'start_peer', mock_start_peer)

    initiator_peer_pool = ParagonPeerPool(
        privkey=INITIATOR_PRIVKEY,
        context=ParagonContext(),
    )
    nodes = [RECEIVER_REMOTE]
    await initiator_peer_pool.connect_to_nodes(nodes)
    # Give the receiver_server a chance to ack the handshake.
    await asyncio.sleep(0.2)

    assert len(started_peers) == 1
    assert len(initiator_peer_pool.connected_nodes) == 1

    # Stop our peer to make sure its pending asyncio tasks are cancelled.
    await list(initiator_peer_pool.connected_nodes.values())[0].cancel()
