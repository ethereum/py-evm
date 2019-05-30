import datetime

import pytest

from p2p.tools.factories import NodeFactory

from trinity.plugins.builtin.network_db.connection.tracker import (
    SQLiteConnectionTracker,
)
from trinity.plugins.builtin.network_db.eth1_peer_db.tracker import (
    MemoryEth1PeerTracker,
)


@pytest.fixture
def remote():
    return NodeFactory()


ZERO_HASH = b'\x00' * 32
ZERO_HASH_HEX = ZERO_HASH.hex()

ZERO_ONE_HASH = b'\x01' * 32
ZERO_ONE_HASH_HEX = ZERO_ONE_HASH.hex()


# is_outbound, last_connected_at, genesis_hash, protocol, protocol_version, network_id
TRACK_ARGS = (True, None, ZERO_HASH, 'eth', 61, 1)
SIMPLE_META = TRACK_ARGS[2:]


@pytest.mark.parametrize('is_outbound', (True, False))
def test_track_peer_connection_persists(remote, is_outbound):
    tracker = MemoryEth1PeerTracker()
    assert not tracker._remote_exists(remote.uri())
    tracker.track_peer_connection(remote, is_outbound, *TRACK_ARGS[1:])
    assert tracker._remote_exists(remote.uri())

    node = tracker._get_remote(remote.uri())
    assert node.uri == remote.uri()
    assert node.is_outbound is is_outbound


@pytest.mark.parametrize('is_outbound', (True, False))
def test_track_peer_connection_does_not_clobber_existing_record(remote, is_outbound):
    tracker = MemoryEth1PeerTracker()
    assert not tracker._remote_exists(remote.uri())
    tracker.track_peer_connection(remote, is_outbound, *TRACK_ARGS[1:])

    original = tracker._get_remote(remote.uri())
    assert original.is_outbound is is_outbound

    tracker.track_peer_connection(remote, not is_outbound, *TRACK_ARGS[1:])

    updated = tracker._get_remote(remote.uri())
    assert updated.is_outbound is is_outbound


def test_track_peer_connection_metadata(remote, caplog):
    tracker = MemoryEth1PeerTracker()
    tracker.track_peer_connection(remote, *TRACK_ARGS)

    node = tracker._get_remote(remote.uri())
    assert node.genesis_hash == ZERO_HASH_HEX
    assert node.protocol == 'eth'
    assert node.protocol_version == 61
    assert node.network_id == 1


def test_track_peer_connection_metadata_updates(remote, caplog):
    tracker = MemoryEth1PeerTracker()
    tracker.track_peer_connection(remote, *TRACK_ARGS)

    node = tracker._get_remote(remote.uri())
    assert node.genesis_hash == ZERO_HASH_HEX
    assert node.protocol == 'eth'
    assert node.protocol_version == 61
    assert node.network_id == 1

    tracker.track_peer_connection(remote, True, None, ZERO_ONE_HASH, 'les', 60, 2)

    updated_node = tracker._get_remote(remote.uri())
    assert updated_node.genesis_hash == ZERO_ONE_HASH_HEX
    assert updated_node.protocol == 'les'
    assert updated_node.protocol_version == 60
    assert updated_node.network_id == 2


def test_track_peer_connection_tracks_last_connected(remote, caplog):
    tracker = MemoryEth1PeerTracker()
    now = datetime.datetime.utcnow()
    tracker.track_peer_connection(remote, True, now, *SIMPLE_META)

    node = tracker._get_remote(remote.uri())
    assert node.last_connected_at == now


def test_track_peer_connection_maintains_last_connected(remote, caplog):
    tracker = MemoryEth1PeerTracker()
    now = datetime.datetime.utcnow()
    tracker.track_peer_connection(remote, True, now, *SIMPLE_META)

    node = tracker._get_remote(remote.uri())
    assert node.last_connected_at == now

    tracker.track_peer_connection(remote, True, None, *SIMPLE_META)
    updated_node = tracker._get_remote(remote.uri())
    assert updated_node.last_connected_at == now


def test_track_peer_connection_updates_last_connected(remote, caplog):
    tracker = MemoryEth1PeerTracker()
    now = datetime.datetime.utcnow()
    tracker.track_peer_connection(remote, True, now, *SIMPLE_META)

    node = tracker._get_remote(remote.uri())
    assert node.last_connected_at == now

    later = now + datetime.timedelta(seconds=300)
    tracker.track_peer_connection(remote, True, later, *SIMPLE_META)
    updated_node = tracker._get_remote(remote.uri())
    assert updated_node.last_connected_at == later


@pytest.mark.asyncio
async def do_tracker_peer_query_test(tracker_params,
                                     good_remotes,
                                     bad_remotes,
                                     blacklist_records=(),
                                     connected_remotes=None):
    tracker = MemoryEth1PeerTracker(**tracker_params)

    for remote, is_outbound, meta_params in good_remotes:
        tracker.track_peer_connection(remote, is_outbound, None, *meta_params)

    for remote, is_outbound, meta_params in bad_remotes:
        tracker.track_peer_connection(remote, is_outbound, None, *meta_params)

    # use the same in-memory database
    blacklist_tracker = SQLiteConnectionTracker(tracker.session)
    for remote, delta_seconds in blacklist_records:
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=delta_seconds)
        blacklist_tracker._create_record(remote, expires_at, 'test')

    candidates = tuple(
        await tracker.get_peer_candidates(
            num_requested=10,
            connected_remotes=connected_remotes or set(),
        )
    )
    just_good_remotes = tuple(r[0] for r in good_remotes)
    just_bad_remotes = tuple(r[0] for r in bad_remotes)
    assert len(candidates) == len(just_good_remotes)
    for remote in just_good_remotes:
        assert remote in candidates
    for remote in just_bad_remotes:
        assert remote not in candidates


@pytest.mark.asyncio
async def test_getting_peer_candidates_no_filter():
    await do_tracker_peer_query_test(
        tracker_params={},
        good_remotes=(
            (NodeFactory(), True, SIMPLE_META),
            (NodeFactory(), True, SIMPLE_META),
            (NodeFactory(), True, SIMPLE_META),
        ),
        bad_remotes=(),
    )


@pytest.mark.asyncio
async def test_getting_peer_candidates_excludes_non_outbound():
    await do_tracker_peer_query_test(
        tracker_params={},
        good_remotes=(
            (NodeFactory(), True, SIMPLE_META),
            (NodeFactory(), True, SIMPLE_META),
        ),
        bad_remotes=(
            (NodeFactory(), False, SIMPLE_META),
        ),
    )


@pytest.mark.asyncio
async def test_getting_peer_candidates_excludes_genesis_hash_mismatch():
    await do_tracker_peer_query_test(
        tracker_params={'genesis_hash': ZERO_HASH},
        good_remotes=(
            (NodeFactory(), True, SIMPLE_META),
            (NodeFactory(), True, SIMPLE_META),
        ),
        bad_remotes=(
            (NodeFactory(), True, (ZERO_ONE_HASH, 'eth', 61, 1)),
        ),
    )


@pytest.mark.asyncio
async def test_getting_peer_candidates_excludes_protocol_mismatch():
    await do_tracker_peer_query_test(
        tracker_params={'protocols': ('eth',)},
        good_remotes=(
            (NodeFactory(), True, SIMPLE_META),
            (NodeFactory(), True, SIMPLE_META),
        ),
        bad_remotes=(
            (NodeFactory(), True, (ZERO_HASH, 'les', 61, 1)),
        ),
    )


@pytest.mark.asyncio
async def test_getting_peer_candidates_matches_multiple_protocols():
    await do_tracker_peer_query_test(
        tracker_params={'protocols': ('eth', 'les')},
        good_remotes=(
            (NodeFactory(), True, (ZERO_HASH, 'eth', 61, 1)),
            (NodeFactory(), True, (ZERO_HASH, 'les', 61, 1)),
        ),
        bad_remotes=(
            (NodeFactory(), True, (ZERO_HASH, 'bcc', 61, 1)),
        ),
    )


@pytest.mark.asyncio
async def test_getting_peer_candidates_excludes_protocol_version_mismatch():
    await do_tracker_peer_query_test(
        tracker_params={'protocol_versions': (60, 61)},
        good_remotes=(
            (NodeFactory(), True, (ZERO_HASH, 'eth', 60, 1)),
            (NodeFactory(), True, (ZERO_HASH, 'eth', 61, 1)),
        ),
        bad_remotes=(
            (NodeFactory(), True, (ZERO_HASH, 'eth', 62, 1)),
        ),
    )


@pytest.mark.asyncio
async def test_getting_peer_candidates_excludes_network_id_mismatch():
    await do_tracker_peer_query_test(
        tracker_params={'network_id': 1},
        good_remotes=(
            (NodeFactory(), True, SIMPLE_META),
            (NodeFactory(), True, SIMPLE_META),
        ),
        bad_remotes=(
            (NodeFactory(), True, (ZERO_HASH, 'eth', 62, 2)),
        ),
    )


@pytest.mark.asyncio
async def test_getting_peer_candidates_complex_query():
    await do_tracker_peer_query_test(
        tracker_params={
            'genesis_hash': ZERO_HASH,
            'protocols': ['eth'],
            'protocol_versions': [61],
            'network_id': 1,
        },
        good_remotes=(
            (NodeFactory(), True, SIMPLE_META),
            (NodeFactory(), True, SIMPLE_META),
        ),
        bad_remotes=(
            (NodeFactory(), False, SIMPLE_META),  # inbound peer
            (NodeFactory(), True, (ZERO_HASH, 'les', 61, 1)),  # wrong protocol
            (NodeFactory(), True, (ZERO_HASH, 'eth', 60, 1)),  # wrong protocol version
            (NodeFactory(), True, (ZERO_HASH, 'eth', 61, 2)),  # wrong network_id
        ),
    )


@pytest.mark.asyncio
async def test_excludes_blacklisted_peers_from_candidates():
    remote_b = NodeFactory()
    await do_tracker_peer_query_test(
        tracker_params={},
        good_remotes=(
            (NodeFactory(), True, SIMPLE_META),
            (NodeFactory(), True, SIMPLE_META),
        ),
        bad_remotes=(
            (remote_b, True, SIMPLE_META),
        ),
        blacklist_records=(
            (remote_b, 10),  # blacklisted for 10 seconds
        )
    )


@pytest.mark.asyncio
async def test_includes_expired_blacklisted_from_candidates():
    remote_a = NodeFactory()
    await do_tracker_peer_query_test(
        tracker_params={},
        good_remotes=(
            (remote_a, True, SIMPLE_META),
            (NodeFactory(), True, SIMPLE_META),
            (NodeFactory(), True, SIMPLE_META),
        ),
        bad_remotes=(
        ),
        blacklist_records=(
            (remote_a, -10),  # expired blacklist record
        )
    )


@pytest.mark.asyncio
async def test_candidate_selection_with_mixed_blacklisted_remotes():
    remote_a = NodeFactory()
    remote_b = NodeFactory()
    remote_c = NodeFactory()
    remote_d = NodeFactory()
    await do_tracker_peer_query_test(
        tracker_params={},
        good_remotes=(
            (remote_a, True, SIMPLE_META),
            (NodeFactory(), True, SIMPLE_META),
            (remote_c, True, SIMPLE_META),
            (NodeFactory(), True, SIMPLE_META),
        ),
        bad_remotes=(
            (remote_b, True, SIMPLE_META),
            (remote_d, True, SIMPLE_META),
        ),
        blacklist_records=(
            (remote_a, -5),  # expired blacklist record
            (remote_b, 10),  # expired blacklist record
            (remote_c, -20),  # expired blacklist record
            (remote_d, 25),  # expired blacklist record
        )
    )


@pytest.mark.asyncio
async def test_getting_peer_candidates_excludes_already_connected():
    remote_a = NodeFactory()
    await do_tracker_peer_query_test(
        tracker_params={},
        good_remotes=(
            (NodeFactory(), True, SIMPLE_META),
            (NodeFactory(), True, SIMPLE_META),
        ),
        bad_remotes=(
            (remote_a, True, SIMPLE_META),
        ),
        connected_remotes=(remote_a,),
    )
