import asyncio

import pytest

from evm.chains.shard import Shard
from evm.db.backends.memory import MemoryDB
from evm.db.shard import ShardDB

from evm.utils.blobs import (
    calc_chunk_root,
)
from evm.utils.padding import (
    zpad_right,
)

from p2p.sharding import (
    Collations,
    ShardingPeer,
    ShardingProtocol,
    ShardSyncer,
)
from p2p.cancel_token import (
    CancelToken,
)

from p2p.exceptions import (
    HandshakeFailure,
)

from evm.rlp.headers import CollationHeader
from evm.rlp.collations import Collation

from evm.constants import (
    COLLATION_SIZE,
)

from tests.p2p.peer_helpers import (
    get_directly_linked_peers,
    get_directly_linked_peers_without_handshake,
    MockPeerPoolWithConnectedPeers,
)


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
async def test_collation_requests(request, event_loop):
    # setup two peers
    sender, receiver = await get_directly_linked_peers(
        request,
        event_loop,
        ShardingPeer,
        None,
        ShardingPeer,
        None,
    )
    receiver_peer_pool = MockPeerPoolWithConnectedPeers([receiver])

    # setup shard db for request receiving node
    receiver_db = ShardDB(MemoryDB())
    receiver_shard = Shard(receiver_db, 0)

    # create three collations and add two to the shard of the receiver
    # body is shared to avoid unnecessary chunk root calculation
    body = zpad_right(b"body", COLLATION_SIZE)
    chunk_root = calc_chunk_root(body)
    c1 = Collation(CollationHeader(0, chunk_root, 0, zpad_right(b"proposer1", 20)), body)
    c2 = Collation(CollationHeader(0, chunk_root, 1, zpad_right(b"proposer2", 20)), body)
    c3 = Collation(CollationHeader(0, chunk_root, 2, zpad_right(b"proposer3", 20)), body)
    for collation in [c1, c2]:
        receiver_shard.add_collation(collation)

    # start shard syncer
    receiver_syncer = ShardSyncer(receiver_shard, receiver_peer_pool)
    asyncio.ensure_future(receiver_syncer.run())

    def finalizer():
        event_loop.run_until_complete(receiver_syncer.cancel())
    request.addfinalizer(finalizer)

    cancel_token = CancelToken("test")

    # request single collation
    received_collations = await asyncio.wait_for(
        sender.get_collations([c1.hash], cancel_token),
        timeout=1,
    )
    assert received_collations == set([c1])

    # request multiple collations
    received_collations = await asyncio.wait_for(
        sender.get_collations([c1.hash, c2.hash], cancel_token),
        timeout=1,
    )
    assert received_collations == set([c1, c2])

    # request no collations
    received_collations = await asyncio.wait_for(
        sender.get_collations([], cancel_token),
        timeout=1,
    )
    assert received_collations == set()

    # request unknown collation
    received_collations = await asyncio.wait_for(
        sender.get_collations([c3.hash], cancel_token),
        timeout=1,
    )
    assert received_collations == set()

    # request multiple collations, including unknown one
    received_collations = await asyncio.wait_for(
        sender.get_collations([c1.hash, c2.hash, c3.hash], cancel_token),
        timeout=1,
    )
    assert received_collations == set([c1, c2])


@pytest.mark.asyncio
@pytest.mark.parametrize("connections", [
    ([(0, 1)]),  # two peers connected directly with each other
    ([(0, 1), (0, 2), (1, 2)]),  # three fully connected peers
    ([(0, 1), (1, 2)]),  # three peers in a row
    # 10 nodes randomly connected to ~4 peers each
    # TODO: do something against time out because of long chunk root calculation time
    # (10, set(tuple(sorted(random.sample(range(10), 2))) for _ in range(10 * 4))),
])
async def test_shard_syncer(connections, request, event_loop):
    peers_by_server = {}
    for server_id1, server_id2 in connections:
        peer1, peer2 = await get_directly_linked_sharding_peers(request, event_loop)
        peers_by_server.setdefault(server_id1, []).append(peer1)
        peers_by_server.setdefault(server_id2, []).append(peer2)

    syncers = []
    for _, peers in sorted(peers_by_server.items()):
        peer_pool = MockPeerPoolWithConnectedPeers(peers)
        shard_db = ShardDB(MemoryDB())
        syncer = ShardSyncer(Shard(shard_db, 0), peer_pool)
        syncers.append(syncer)
        asyncio.ensure_future(syncer.run())

    def finalizer():
        event_loop.run_until_complete(
            asyncio.gather(*[syncer.cancel() for syncer in syncers]))
    request.addfinalizer(finalizer)

    # let each node propose and check that collation appears at all other nodes
    for proposer in syncers:
        collation = proposer.propose()
        await asyncio.wait_for(asyncio.gather(*[
            syncer.collations_received_event.wait()
            for syncer in syncers
            if syncer != proposer
        ]), timeout=2)
        for syncer in syncers:
            assert syncer.shard.get_collation_by_hash(collation.hash) == collation


async def get_directly_linked_sharding_peers(request, event_loop):
    return await get_directly_linked_peers(
        request, event_loop, ShardingPeer, None, ShardingPeer, None,)
