import asyncio
import os

import pytest

import rlp
from rlp import sedes

from evm.chains.mainnet import MAINNET_GENESIS_HEADER
from evm.db.backends.memory import MemoryDB
from evm.db.chain import BaseChainDB
from evm.rlp.headers import BlockHeader
from evm.utils.keccak import (
    keccak,
)
from evm.p2p import auth
from evm.p2p import constants
from evm.p2p import ecies
from evm.p2p import kademlia
from evm.p2p.les import (
    LESProtocol,
    Announce,
    BlockHeaders,
    BlockBodies,
    GetBlockBodies,
    GetBlockHeaders,
    Status,
)
from evm.p2p.peer import LESPeer
from evm.p2p.protocol import Protocol
from evm.p2p.p2p_proto import P2PProtocol


# A full header sync may involve several round trips, so we must be willing to wait a little bit
# for them.
HEADER_SYNC_TIMEOUT = 3


class LESProtocolFull(LESProtocol):
    _commands = [Status, Announce, BlockHeaders, BlockBodies, GetBlockHeaders, GetBlockBodies]

    def send_announce(self, block_hash, block_number, total_difficulty, reorg_depth):
        data = {
            'head_hash': block_hash,
            'head_number': block_number,
            'head_td': total_difficulty,
            'reorg_depth': reorg_depth,
            'params': [],
        }
        header, body = Announce(self.cmd_id_offset).encode(data)
        self.send(header, body)

    def send_block_headers(self, headers, buffer_value, request_id):
        data = {
            'request_id': request_id,
            'headers': headers,
            'buffer_value': buffer_value,
        }
        header, body = BlockHeaders(self.cmd_id_offset).encode(data)
        self.send(header, body)


class LESPeerServing(LESPeer):
    """A LESPeer that can send announcements and responds to GetBlockHeaders msgs.

    Used to test our LESPeer implementation. Tests should call .send_announce(), optionally
    specifying a block number to use as the chain's head and then use the helper function
    wait_for_head() to wait until the client peer has synced all headers up to the announced head.
    """
    conn_idle_timeout = 2
    reply_timeout = 1
    max_headers_fetch = 20
    _supported_sub_protocols = [LESProtocolFull]
    _head_number = None

    @property
    def head_number(self):
        if self._head_number is not None:
            return self._head_number
        else:
            return self.chaindb.get_canonical_head().block_number

    def send_announce(self, head_number=None, reorg_depth=0):
        if head_number is not None:
            self._head_number = head_number
        header = self.chaindb.get_canonical_block_header_by_number(self.head_number)
        total_difficulty = self.chaindb.get_score(header.hash)
        self.les_proto.send_announce(
            header.hash, header.block_number, total_difficulty, reorg_depth)

    def handle_msg(self, cmd, msg):
        if isinstance(cmd, GetBlockHeaders):
            self.handle_get_block_headers(msg)
        else:
            super(LESPeerServing, self).handle_msg(cmd, msg)

    def handle_get_block_headers(self, msg):
        query = msg['query']
        if query.reverse:
            start = max(0, query.block - query.max_headers)
            # Shift our range() limits by 1 because we want to include the requested block number
            # in the list of block numbers.
            block_numbers = reversed(range(start + 1, query.block + 1))
        else:
            end = min(self.head_number + 1, query.block + query.max_headers)
            block_numbers = range(query.block, end)

        headers = tuple(
            self.chaindb.get_canonical_block_header_by_number(i)
            for i in block_numbers
        )
        self.les_proto.send_block_headers(headers, buffer_value=0, request_id=msg['request_id'])


async def get_directly_linked_peers(chaindb1=None, chaindb2=None):
    """Create two LESPeers with their readers/writers connected directly.

    The first peer's reader will write directly to the second's writer, and vice-versa.
    """
    if chaindb1 is None:
        chaindb1 = BaseChainDB(MemoryDB())
        chaindb1.persist_header_to_db(MAINNET_GENESIS_HEADER)
    if chaindb2 is None:
        chaindb2 = BaseChainDB(MemoryDB())
        chaindb2.persist_header_to_db(MAINNET_GENESIS_HEADER)
    peer1_private_key = ecies.generate_privkey()
    peer2_private_key = ecies.generate_privkey()
    peer1_remote = kademlia.Node(
        peer2_private_key.public_key, kademlia.Address('0.0.0.0', 0, 0))
    peer2_remote = kademlia.Node(
        peer1_private_key.public_key, kademlia.Address('0.0.0.0', 0, 0))
    initiator = auth.HandshakeInitiator(peer1_remote, peer1_private_key)
    peer2_reader = asyncio.StreamReader()
    peer1_reader = asyncio.StreamReader()
    # Link the peer1's writer to the peer2's reader, and the peer2's writer to the
    # peer1's reader.
    peer2_writer = type(
        "mock-streamwriter",
        (object,),
        {"write": peer1_reader.feed_data,
         "close": lambda: None}
    )
    peer1_writer = type(
        "mock-streamwriter",
        (object,),
        {"write": peer2_reader.feed_data,
         "close": lambda: None}
    )

    peer1, peer2 = None, None
    handshake_finished = asyncio.Event()

    async def do_handshake():
        nonlocal peer1, peer2
        aes_secret, mac_secret, egress_mac, ingress_mac = await auth._handshake(
            initiator, peer1_reader, peer1_writer)

        # Need to copy those before we pass them on to the Peer constructor because they're
        # mutable. Also, the 2nd peer's ingress/egress MACs are reversed from the first peer's.
        peer2_ingress = egress_mac.copy()
        peer2_egress = ingress_mac.copy()

        peer1 = LESPeerServing(
            remote=peer1_remote, privkey=peer1_private_key, reader=peer1_reader,
            writer=peer1_writer, aes_secret=aes_secret, mac_secret=mac_secret,
            egress_mac=egress_mac, ingress_mac=ingress_mac, chaindb=chaindb1,
            network_id=1)

        peer2 = LESPeerServing(
            remote=peer2_remote, privkey=peer2_private_key, reader=peer2_reader,
            writer=peer2_writer, aes_secret=aes_secret, mac_secret=mac_secret,
            egress_mac=peer2_egress, ingress_mac=peer2_ingress, chaindb=chaindb2,
            network_id=1)

        handshake_finished.set()

    asyncio.ensure_future(do_handshake())

    responder = auth.HandshakeResponder(peer2_remote, peer2_private_key)
    auth_msg = await peer2_reader.read(constants.ENCRYPTED_AUTH_MSG_LEN)
    peer1_ephemeral_pubkey, peer1_nonce = responder.decode_authentication(auth_msg)

    peer2_nonce = keccak(os.urandom(constants.HASH_LEN))
    auth_ack_msg = responder.create_auth_ack_message(peer2_nonce)
    auth_ack_ciphertext = responder.encrypt_auth_ack_message(auth_ack_msg)
    peer2_writer.write(auth_ack_ciphertext)

    await handshake_finished.wait()

    # Perform the base protocol (P2P) handshake.
    peer1.base_protocol.send_handshake()
    peer2.base_protocol.send_handshake()
    msg1 = await peer1.read_msg()
    peer1.process_msg(msg1)
    msg2 = await peer2.read_msg()
    peer2.process_msg(msg2)

    # Now send the handshake msg for each enabled sub-protocol.
    for proto in peer1.enabled_sub_protocols:
        proto.send_handshake(peer1.head_info)
    for proto in peer2.enabled_sub_protocols:
        proto.send_handshake(peer2.head_info)

    return peer1, peer2


@pytest.mark.asyncio
async def test_directly_linked_peers():
    peer1, peer2 = await get_directly_linked_peers()
    assert len(peer1.enabled_sub_protocols) == 1
    assert peer1.les_proto is not None
    assert peer1.les_proto.name == LESProtocol.name
    assert peer1.les_proto.version == LESProtocol.version
    assert [(proto.name, proto.version) for proto in peer1.enabled_sub_protocols] == [
        (proto.name, proto.version) for proto in peer2.enabled_sub_protocols]


async def get_linked_and_running_peers(request, event_loop, chaindb1=None, chaindb2=None):
    peer1, peer2 = await get_directly_linked_peers(chaindb1, chaindb2)
    asyncio.ensure_future(peer1.start())
    asyncio.ensure_future(peer2.start())

    def finalizer():
        async def afinalizer():
            await peer1.stop_and_wait_until_finished()
            await peer2.stop_and_wait_until_finished()
        event_loop.run_until_complete(afinalizer())
    request.addfinalizer(finalizer)

    return peer1, peer2


@pytest.mark.asyncio
async def test_incremental_header_sync(request, event_loop, chaindb_mainnet_100):
    # Here, server will be a peer with a pre-populated chaindb, and we'll use it to send Announce
    # msgs to the client, which will then ask the server for any headers it's missing until their
    # chaindbs are in sync.
    server, client = await get_linked_and_running_peers(
        request, event_loop, chaindb1=None, chaindb2=None)

    # We start the client/server with fresh chaindbs above because we don't want them to start
    # syncing straight away -- instead we want to manually trigger incremental syncs by having the
    # server send Announce messages. We're now ready to give our server a populated chaindb.
    server.chaindb = chaindb_mainnet_100

    # The server now announces block #10 as the new head...
    server.send_announce(head_number=10)

    # ... and we wait for the client to process that and request all headers it's missing up to
    # block #10.
    header_10 = server.chaindb.get_canonical_block_header_by_number(10)
    await wait_for_head(client.chaindb, header_10)
    assert_canonical_chains_are_equal(client.chaindb, server.chaindb, 10)

    # Now the server announces block 100 as its current head...
    server.send_announce(head_number=100)

    # ... and the client should then fetch headers from 10-100.
    header_100 = server.chaindb.get_canonical_block_header_by_number(100)
    await wait_for_head(client.chaindb, header_100)
    assert_canonical_chains_are_equal(client.chaindb, server.chaindb, 100)


@pytest.mark.asyncio
async def test_full_header_sync_and_reorg(request, event_loop, chaindb_mainnet_100):
    # Here we create our server with a populated chaindb, so upon startup it will announce its
    # chain head and the client will fetch all headers
    server, client = await get_linked_and_running_peers(
        request, event_loop, chaindb1=chaindb_mainnet_100, chaindb2=None)

    # ... and our client should then fetch all headers.
    head = server.chaindb.get_canonical_head()
    await wait_for_head(client.chaindb, head)
    assert_canonical_chains_are_equal(client.chaindb, server.chaindb, head.block_number)

    head_parent = server.chaindb.get_block_header_by_hash(head.parent_hash)
    difficulty = head.difficulty + 1
    new_head = BlockHeader.from_parent(
        head_parent, head_parent.gas_limit, difficulty=difficulty,
        timestamp=head.timestamp, coinbase=head.coinbase)
    server.chaindb.persist_header_to_db(new_head)
    assert server.chaindb.get_canonical_head() == new_head
    server.send_announce(head_number=head.block_number, reorg_depth=1)

    await wait_for_head(client.chaindb, new_head)
    assert_canonical_chains_are_equal(client.chaindb, server.chaindb, new_head.block_number)


@pytest.mark.asyncio
async def test_header_sync_with_multi_peers(request, event_loop, chaindb_mainnet_100):
    # In this test we start with one of our peers announcing block #100, and we sync all
    # headers up to that...
    server, client = await get_linked_and_running_peers(
        request, event_loop, chaindb1=chaindb_mainnet_100, chaindb2=None)

    head = server.chaindb.get_canonical_head()
    await wait_for_head(client.chaindb, head)
    assert_canonical_chains_are_equal(client.chaindb, server.chaindb, head.block_number)

    # Now a second peer comes along and announces block #100 as well, but it's different
    # from the one we already have, so we need to fetch that too. And since it has a higher total
    # difficulty than the current head, it will become our new chain head.
    server2_chaindb = server.chaindb
    head_parent = server2_chaindb.get_block_header_by_hash(head.parent_hash)
    difficulty = head.difficulty + 1
    new_head = BlockHeader.from_parent(
        head_parent, head_parent.gas_limit, difficulty=difficulty,
        timestamp=head.timestamp, coinbase=head.coinbase)
    server2_chaindb.persist_header_to_db(new_head)
    assert server2_chaindb.get_canonical_head() == new_head
    server2, client2 = await get_linked_and_running_peers(
        request, event_loop, chaindb1=server2_chaindb, chaindb2=client.chaindb)

    await wait_for_head(client.chaindb, new_head)
    assert_canonical_chains_are_equal(client.chaindb, server2.chaindb, new_head.block_number)


@pytest.mark.asyncio
async def test_les_handshake():
    peer1, peer2 = await get_directly_linked_peers()
    # The peers above have already performed the sub-protocol agreement, and sent the handshake
    # msg for each enabled sub protocol -- in this case that's the Status msg of the LES protocol.
    msg = await peer1.read_msg()
    cmd_id = rlp.decode(msg[:1], sedes=sedes.big_endian_int)
    proto = peer1.get_protocol_for(cmd_id)
    assert cmd_id == proto.cmd_by_class[Status].cmd_id


def test_sub_protocol_matching():
    peer = ProtoMatchingPeer([LESProtocol, LESProtocolV2, ETHProtocol63])

    peer.match_protocols([
        (LESProtocol.name, LESProtocol.version),
        (LESProtocolV2.name, LESProtocolV2.version),
        (LESProtocolV3.name, LESProtocolV3.version),
        (ETHProtocol63.name, ETHProtocol63.version),
        ('unknown', 1),
    ])

    assert len(peer.enabled_sub_protocols) == 2
    eth_proto, les_proto = peer.enabled_sub_protocols
    assert isinstance(eth_proto, ETHProtocol63)
    assert eth_proto.cmd_id_offset == peer.base_protocol.cmd_length

    assert isinstance(les_proto, LESProtocolV2)
    assert les_proto.cmd_id_offset == peer.base_protocol.cmd_length + eth_proto.cmd_length


class LESProtocolV2(LESProtocol):
    version = 2

    def send_handshake(self):
        pass


class LESProtocolV3(LESProtocol):
    version = 3

    def send_handshake(self):
        pass


class ETHProtocol63(Protocol):
    name = b'eth'
    version = 63
    cmd_length = 15

    def send_handshake(self):
        pass


class ProtoMatchingPeer(LESPeer):

    def __init__(self, supported_sub_protocols):
        self._supported_sub_protocols = supported_sub_protocols
        self.base_protocol = MockP2PProtocol(self)
        self.enabled_sub_protocols = []


class MockP2PProtocol(P2PProtocol):

    def send_handshake(self):
        pass


def assert_canonical_chains_are_equal(chaindb1, chaindb2, block_number=None):
    """Assert that the canonical chains in both DBs are identical up to block_number."""
    if block_number is None:
        block_number = chaindb1.get_canonical_head().block_number
        assert block_number == chaindb2.get_canonical_head().block_number
    for i in range(0, block_number + 1):
        assert chaindb1.get_canonical_block_header_by_number(i) == (
            chaindb2.get_canonical_block_header_by_number(i))


@pytest.fixture
def chaindb_mainnet_100():
    """Return a chaindb with mainnet headers numbered from 0 to 100."""
    here = os.path.dirname(__file__)
    headers_rlp = open(os.path.join(here, 'testdata', 'sample_1000_headers_rlp'), 'r+b').read()
    headers = rlp.decode(headers_rlp, sedes=sedes.CountableList(BlockHeader))
    chaindb = BaseChainDB(MemoryDB())
    for i in range(0, 101):
        chaindb.persist_header_to_db(headers[i])
    return chaindb


async def wait_for_head(chaindb, header):
    async def wait_loop():
        while chaindb.get_canonical_head() != header:
            await asyncio.sleep(0.1)
    await asyncio.wait_for(wait_loop(), HEADER_SYNC_TIMEOUT)
