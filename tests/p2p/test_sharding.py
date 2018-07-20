import asyncio
import itertools

import pytest

from eth.chains.shard import Shard
from eth.db.backends.memory import MemoryDB
from eth.db.shard import ShardDB

from eth.utils.blobs import (
    calc_chunk_root,
)
from eth.utils.padding import (
    zpad_right,
)

from p2p.sharding_protocol import (
    ShardingProtocol,
    GetCollations,
    NewCollationHashes,
)
from p2p.sharding_peer import (
    ShardingPeer,
)
from p2p.shard_syncer import (
    ShardSyncer,
)
from p2p.cancel_token import (
    CancelToken,
)

from p2p.exceptions import (
    HandshakeFailure,
)

from eth.rlp.headers import CollationHeader
from eth.rlp.collations import Collation

from eth.constants import (
    COLLATION_SIZE,
)

from tests.p2p.peer_helpers import (
    get_directly_linked_peers,
    get_directly_linked_peers_without_handshake,
    MockPeerPoolWithConnectedPeers,
    SamplePeerSubscriber,
)

from cytoolz import (
    merge,
)


def generate_collations():
    explicit_params = {}
    for period in itertools.count():
        default_params = {
            "shard_id": 0,
            "period": period,
            "body": zpad_right(b"body%d" % period, COLLATION_SIZE),
            "proposer_address": zpad_right(b"proposer%d" % period, 20),
        }
        # only calculate chunk root if it wouldn't be replaced anyway
        if "chunk_root" not in explicit_params:
            default_params["chunk_root"] = calc_chunk_root(default_params["body"])

        params = merge(default_params, explicit_params)
        header = CollationHeader(
            shard_id=params["shard_id"],
            chunk_root=params["chunk_root"],
            period=params["period"],
            proposer_address=params["proposer_address"],
        )
        collation = Collation(header, params["body"])
        explicit_params = (yield collation) or {}


collations = generate_collations()
next(collations)  # yield once so that we can send values to the generator


async def get_directly_linked_sharding_peers(request, event_loop):
    return await get_directly_linked_peers(
        request, event_loop, ShardingPeer, None, ShardingPeer, None,)


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
            self.sub_proto.send_collations(0, [])

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
    sender, receiver = await get_directly_linked_sharding_peers(request, event_loop)
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
async def test_new_collations_notification(request, event_loop):
    # setup a-b-c topology
    peer_a_b, peer_b_a = await get_directly_linked_sharding_peers(request, event_loop)
    peer_b_c, peer_c_b = await get_directly_linked_sharding_peers(request, event_loop)
    peer_c_b_subscriber = SamplePeerSubscriber()
    peer_c_b.add_subscriber(peer_c_b_subscriber)
    peer_pool_b = MockPeerPoolWithConnectedPeers([peer_b_a, peer_b_c])

    # setup shard dbs at b
    shard_db = ShardDB(MemoryDB())
    shard = Shard(shard_db, 0)

    # start shard syncer
    syncer = ShardSyncer(shard, peer_pool_b)
    asyncio.ensure_future(syncer.run())

    def finalizer():
        event_loop.run_until_complete(syncer.cancel())
    request.addfinalizer(finalizer)

    # send collation from a to b and check that c gets notified
    c1 = next(collations)
    peer_a_b.sub_proto.send_collations(0, [c1])
    peer, cmd, msg = await asyncio.wait_for(
        peer_c_b_subscriber.msg_queue.get(),
        timeout=1,
    )
    assert peer == peer_c_b
    assert isinstance(cmd, NewCollationHashes)
    assert msg["collation_hashes_and_periods"] == ((c1.hash, c1.period),)

    # check that c won't be notified about c1 again
    c2 = next(collations)
    peer_a_b.sub_proto.send_collations(0, [c1, c2])
    peer, cmd, msg = await asyncio.wait_for(
        peer_c_b_subscriber.msg_queue.get(),
        timeout=1,
    )
    assert peer == peer_c_b
    assert isinstance(cmd, NewCollationHashes)
    assert msg["collation_hashes_and_periods"] == ((c2.hash, c2.period),)


@pytest.mark.asyncio
async def test_syncer_requests_new_collations(request, event_loop):
    # setup a-b topology
    peer_a_b, peer_b_a = await get_directly_linked_sharding_peers(request, event_loop)
    peer_a_b_subscriber = SamplePeerSubscriber()
    peer_a_b.add_subscriber(peer_a_b_subscriber)
    peer_pool_b = MockPeerPoolWithConnectedPeers([peer_b_a])

    # setup shard dbs at b
    shard_db = ShardDB(MemoryDB())
    shard = Shard(shard_db, 0)

    # start shard syncer
    syncer = ShardSyncer(shard, peer_pool_b)
    asyncio.ensure_future(syncer.run())

    def finalizer():
        event_loop.run_until_complete(syncer.cancel())
    request.addfinalizer(finalizer)

    # notify b about new hashes at a and check that it requests them
    hashes_and_periods = ((b"\xaa" * 32, 0),)
    peer_a_b.sub_proto.send_new_collation_hashes(hashes_and_periods)
    peer, cmd, msg = await asyncio.wait_for(
        peer_a_b_subscriber.msg_queue.get(),
        timeout=1,
    )
    assert peer == peer_a_b
    assert isinstance(cmd, GetCollations)
    assert msg["collation_hashes"] == (hashes_and_periods[0][0],)


@pytest.mark.asyncio
async def test_syncer_proposing(request, event_loop):
    # setup a-b topology
    peer_a_b, peer_b_a = await get_directly_linked_sharding_peers(request, event_loop)
    peer_a_b_subscriber = SamplePeerSubscriber()
    peer_a_b.add_subscriber(peer_a_b_subscriber)
    peer_pool_b = MockPeerPoolWithConnectedPeers([peer_b_a])

    # setup shard dbs at b
    shard_db = ShardDB(MemoryDB())
    shard = Shard(shard_db, 0)

    # start shard syncer
    syncer = ShardSyncer(shard, peer_pool_b)
    asyncio.ensure_future(syncer.run())

    def finalizer():
        event_loop.run_until_complete(syncer.cancel())
    request.addfinalizer(finalizer)

    # propose at b and check that it announces its proposal
    await syncer.propose()
    peer, cmd, msg = await asyncio.wait_for(
        peer_a_b_subscriber.msg_queue.get(),
        timeout=1,
    )
    assert peer == peer_a_b
    assert isinstance(cmd, NewCollationHashes)
    assert len(msg["collation_hashes_and_periods"]) == 1
    proposed_hash = msg["collation_hashes_and_periods"][0][0]

    # test that the collation has been added to the shard
    shard.get_collation_by_hash(proposed_hash)
