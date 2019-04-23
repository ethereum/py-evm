import datetime
from pathlib import Path

from p2p.exceptions import (
    HandshakeFailure,
)
from p2p.tools.factories import (
    NodeFactory,
)

from trinity.plugins.builtin.blacklist.tracker import (
    SQLiteConnectionTracker,
    MemoryConnectionTracker,
)
from trinity.db.orm import (
    get_tracking_database,
)


def test_records_failures():
    # where can you get a random pubkey from?
    connection_tracker = MemoryConnectionTracker()

    node = NodeFactory()
    assert connection_tracker.should_connect_to(node) is True

    connection_tracker.record_failure(node, HandshakeFailure())

    assert connection_tracker.should_connect_to(node) is False
    assert connection_tracker._record_exists(node.uri())


def test_memory_does_not_persist():
    node = NodeFactory()

    connection_tracker_a = MemoryConnectionTracker()
    assert connection_tracker_a.should_connect_to(node) is True
    connection_tracker_a.record_failure(node, HandshakeFailure())
    assert connection_tracker_a.should_connect_to(node) is False

    # open a second instance
    connection_tracker_b = MemoryConnectionTracker()

    # the second instance has no memory of the failure
    assert connection_tracker_b.should_connect_to(node) is True
    assert connection_tracker_a.should_connect_to(node) is False


def test_sql_does_persist(tmpdir):
    db_path = Path(str(tmpdir.join("nodedb")))
    node = NodeFactory()

    connection_tracker_a = SQLiteConnectionTracker(get_tracking_database(db_path))
    assert connection_tracker_a.should_connect_to(node) is True
    connection_tracker_a.record_failure(node, HandshakeFailure())
    assert connection_tracker_a.should_connect_to(node) is False
    del connection_tracker_a

    # open a second instance
    connection_tracker_b = SQLiteConnectionTracker(get_tracking_database(db_path))
    # the second instance remembers the failure
    assert connection_tracker_b.should_connect_to(node) is False


def test_timeout_works(monkeypatch):
    node = NodeFactory()

    connection_tracker = MemoryConnectionTracker()
    assert connection_tracker.should_connect_to(node) is True

    connection_tracker.record_failure(node, HandshakeFailure())
    assert connection_tracker.should_connect_to(node) is False

    record = connection_tracker._get_record(node.uri())
    record.expires_at -= datetime.timedelta(seconds=120)
    connection_tracker.session.add(record)
    connection_tracker.session.commit()

    assert connection_tracker.should_connect_to(node) is True
