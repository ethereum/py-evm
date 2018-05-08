import pytest

import asyncio
import collections

from eth_keys import keys
from eth_utils import (
    int_to_big_endian,
)
from evm.utils.padding import (
    pad32,
)

from p2p.cancel_token import (
    CancelToken,
)
from p2p.kademlia import (
    Address,
    Node,
)
from p2p.server import (
    Server,
)
from p2p.exceptions import (
    OperationCancelled,
)

from p2p.sharding import (
    ShardingProtocol,
    ShardingPeer,
    Collations,
    ShardSyncer,
    COLLATION_PERIOD,
)

from p2p.exceptions import (
    HandshakeFailure,
)

from evm.rlp.headers import CollationHeader
from evm.rlp.collations import Collation
from evm.chains.shard import Shard
from evm.db.shard import ShardDB
from evm.db.backends.memory import MemoryDB

from evm.constants import (
    COLLATION_SIZE,
)

from tests.p2p.peer_helpers import (
    get_directly_linked_peers,
    get_directly_linked_peers_without_handshake,
)

from tests.p2p.test_server import (
    get_open_port,
)


@pytest.fixture
def collation_header():
    return CollationHeader(
        0,
        b"\x11" * 32,
        2,
        b"\x33" * 20,
    )


@pytest.fixture
def collation(collation_header):
    body = b"\x00" * COLLATION_SIZE
    return Collation(collation_header, body)


@pytest.fixture
def test_protocol(test_peer):
    return ShardingProtocol(test_peer, 16)


@pytest.mark.asyncio
async def test_handshake():
    peer1, peer2 = await get_directly_linked_peers_without_handshake(
        ShardingPeer,
        None,
        ShardingPeer,
        None,
    )

    await asyncio.gather(
        peer1.do_p2p_handshake(),
        peer2.do_p2p_handshake(),
    )
    await asyncio.gather(
        peer1.do_sub_proto_handshake(),
        peer2.do_sub_proto_handshake(),
    )


@pytest.mark.asyncio
async def test_invalid_handshake():

    class InvalidShardingPeer(ShardingPeer):

        async def send_sub_proto_handshake(self):
            cmd = Collations(self.sub_proto.cmd_id_offset)
            self.send(*cmd.encode([]))

    peer1, peer2 = await get_directly_linked_peers_without_handshake(
        ShardingPeer,
        None,
        InvalidShardingPeer,
        None,
    )

    await asyncio.gather(
        peer1.do_p2p_handshake(),
        peer2.do_p2p_handshake(),
    )
    with pytest.raises(HandshakeFailure):
        await asyncio.gather(
            peer1.do_sub_proto_handshake(),
            peer2.do_sub_proto_handshake(),
        )


@pytest.mark.asyncio
async def test_sending_collations(request, event_loop):
    sender, receiver = await get_directly_linked_peers(
        request,
        event_loop,
        ShardingPeer,
        None,
        ShardingPeer,
        None,
    )

    incoming_collation_queue = asyncio.Queue()
    receiver.set_incoming_collation_queue(incoming_collation_queue)

    c1 = Collation(CollationHeader(0, b"\x11" * 32, 2, b"\x33" * 20), b"\x44" * COLLATION_SIZE)
    c2 = Collation(CollationHeader(1, b"\x11" * 32, 2, b"\x33" * 20), b"\x44" * COLLATION_SIZE)
    c3 = Collation(CollationHeader(2, b"\x11" * 32, 2, b"\x33" * 20), b"\x44" * COLLATION_SIZE)

    sender.sub_proto.send_collations([c1])
    received_c1 = await asyncio.wait_for(incoming_collation_queue.get(), timeout=1)
    assert received_c1 == c1
    assert receiver.known_collation_hashes == set([c1.hash])
    assert incoming_collation_queue.qsize() == 0

    sender.sub_proto.send_collations([c2, c3])
    received_c2 = await asyncio.wait_for(incoming_collation_queue.get(), timeout=1)
    received_c3 = await asyncio.wait_for(incoming_collation_queue.get(), timeout=1)
    assert set([received_c2, received_c3]) == set([c2, c3])
    assert receiver.known_collation_hashes == set([c1.hash, c2.hash, c3.hash])
    assert incoming_collation_queue.qsize() == 0


@pytest.mark.asyncio
async def test_shard_syncer():
    cancel_token = CancelToken("canceltoken")

    PeerTuple = collections.namedtuple("PeerTuple", ["node", "server", "syncer", "syncer_task"])
    n_peers = 2
    peer_tuples = []

    for i in range(n_peers):
        private_key = keys.PrivateKey(pad32(int_to_big_endian(i + 1)))
        port = get_open_port()
        address = Address("127.0.0.1", port, port)

        node = Node(private_key.public_key, address)

        server = Server(
            privkey=private_key,
            server_address=address,
            chaindb=None,
            bootstrap_nodes=[],
            network_id=9324090483,
            min_peers=0,
            peer_class=ShardingPeer
        )
        await server.start()

        shard_db = ShardDB(MemoryDB())
        shard = Shard(shard_db, 0)
        syncer = ShardSyncer(shard, COLLATION_PERIOD * 2, server.peer_pool, cancel_token)
        syncer_task = asyncio.ensure_future(syncer.run())

        peer_tuples.append(PeerTuple(
            node=node,
            server=server,
            syncer=syncer,
            syncer_task=syncer_task,
        ))

    # connect peers to each other
    await peer_tuples[0].server.peer_pool._connect_to_nodes([peer_tuples[1].node])
    assert len(peer_tuples[0].server.peer_pool.peers) == 1

    # both syncers should propose and receive collations
    await asyncio.wait_for(peer_tuples[0].syncer.collations_proposed_event.wait(), 10)
    await asyncio.wait_for(peer_tuples[0].syncer.collations_received_event.wait(), 10)
    await asyncio.wait_for(peer_tuples[1].syncer.collations_proposed_event.wait(), 10)
    await asyncio.wait_for(peer_tuples[1].syncer.collations_received_event.wait(), 10)

    # stop everything
    await peer_tuples[0].server.stop()
    await peer_tuples[1].server.stop()
    cancel_token.trigger()
    with pytest.raises(OperationCancelled):
        await asyncio.gather(*[peer_tuple.syncer_task for peer_tuple in peer_tuples])
