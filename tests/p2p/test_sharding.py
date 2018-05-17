import asyncio

import pytest

from evm.chains.shard import Shard
from evm.db.backends.memory import MemoryDB
from evm.db.shard import ShardDB

from p2p.sharding import (
    Collations,
    ShardingPeer,
    ShardingProtocol,
    ShardSyncer,
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
