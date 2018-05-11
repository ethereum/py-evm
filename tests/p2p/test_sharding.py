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

from p2p.sharding import (
    ShardingProtocol,
    ShardingPeer,
    Collations,
    ShardSyncer,
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

    assert isinstance(peer1.sub_proto, ShardingProtocol)
    assert isinstance(peer2.sub_proto, ShardingProtocol)


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

    c1 = Collation(CollationHeader(0, b"\x11" * 32, 2, b"\x33" * 20), b"\x44" * COLLATION_SIZE)
    c2 = Collation(CollationHeader(1, b"\x11" * 32, 2, b"\x33" * 20), b"\x44" * COLLATION_SIZE)
    c3 = Collation(CollationHeader(2, b"\x11" * 32, 2, b"\x33" * 20), b"\x44" * COLLATION_SIZE)

    sender.sub_proto.send_collations([c1])
    received_c1 = await asyncio.wait_for(receiver.incoming_collation_queue.get(), timeout=1)
    assert received_c1 == c1
    assert receiver.known_collation_hashes == set([c1.hash])

    sender.sub_proto.send_collations([c2, c3])
    received_c2 = await asyncio.wait_for(receiver.incoming_collation_queue.get(), timeout=1)
    received_c3 = await asyncio.wait_for(receiver.incoming_collation_queue.get(), timeout=1)
    assert set([received_c2, received_c3]) == set([c2, c3])
    assert receiver.known_collation_hashes == set([c1.hash, c2.hash, c3.hash])


@pytest.mark.asyncio
@pytest.mark.parametrize("n_peers,connections", [
    (2, [(0, 1)]),  # two peers connected directly with each other
    (3, [(0, 1), (0, 2), (1, 2)]),  # three fully connected peers
    (3, [(0, 1), (1, 2)]),  # three peers in a row
    # 10 nodes randomly connected to ~4 peers each
    # TODO: do something against time out because of long chunk root calculation time
    # (10, set(tuple(sorted(random.sample(range(10), 2))) for _ in range(10 * 4))),
])
async def test_shard_syncer(n_peers, connections):
    cancel_token = CancelToken("canceltoken")

    PeerTuple = collections.namedtuple("PeerTuple", ["node", "server", "syncer", "syncer_task"])
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
        asyncio.ensure_future(server.run())

        shard_db = ShardDB(MemoryDB())
        shard = Shard(shard_db, 0)
        syncer = ShardSyncer(shard, server.peer_pool, cancel_token)
        syncer_task = asyncio.ensure_future(syncer.run())

        peer_tuples.append(PeerTuple(
            node=node,
            server=server,
            syncer=syncer,
            syncer_task=syncer_task,
        ))

    # connect peers to each other
    await asyncio.gather(*[
        peer_tuples[i].server.peer_pool._connect_to_nodes([peer_tuples[j].node])
        for i, j in connections
    ])
    for i, j in connections:
        peer_remotes = [peer.remote for peer in peer_tuples[i].server.peer_pool.peers]
        assert peer_tuples[j].node in peer_remotes

    # let each node propose and check that collation appears at all other nodes
    for proposer in peer_tuples:
        collation = proposer.syncer.propose()
        await asyncio.wait_for(asyncio.gather(*[
            peer_tuple.syncer.collations_received_event.wait()
            for peer_tuple in peer_tuples
            if peer_tuple != proposer
        ]), timeout=10)
        for peer_tuple in peer_tuples:
            assert peer_tuple.syncer.shard.get_collation_by_hash(collation.hash) == collation

    # stop everything
    cancel_token.trigger()
    await asyncio.gather(*[peer_tuple.server.cancel() for peer_tuple in peer_tuples])
    await asyncio.gather(*[peer_tuple.syncer.cancel() for peer_tuple in peer_tuples])
