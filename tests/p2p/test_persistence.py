import datetime
from pathlib import Path
import sqlite3
import pytest
import tempfile

from p2p.exceptions import (
    BadDatabaseError,
    HandshakeFailure,
    WrongGenesisFailure,
)
from p2p import (
    persistence,
)
from p2p.tools.factories import (
    NodeFactory,
)


# do it the long way to enable monkeypatching p2p.persistence.current_time
SQLitePeerInfo = persistence.SQLitePeerInfo
MemoryPeerInfo = persistence.MemoryPeerInfo


def test_timeout_for_failure():
    get_timeout = persistence.timeout_for_failure

    assert get_timeout(WrongGenesisFailure()) == 60 * 60 * 24
    assert get_timeout(HandshakeFailure()) == 10

    class UnknownException(Exception):
        pass

    with pytest.raises(Exception, match="Unknown failure type"):
        assert get_timeout(UnknownException()) is None


@pytest.fixture
def temp_path():
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield Path(tmpdirname)


def test_has_str(temp_path):
    dbpath = temp_path / "nodedb"
    peer_info = SQLitePeerInfo(dbpath)
    assert str(peer_info) == f'<SQLitePeerInfo({str(dbpath)})>'


def test_reads_schema(temp_path):
    dbpath = temp_path / "nodedb"

    # this will setup the tables
    peer_info = SQLitePeerInfo(dbpath)
    peer_info.close()

    # this runs a quick check that the tables were setup
    peer_info = SQLitePeerInfo(dbpath)
    peer_info.close()


def test_fails_when_schema_version_is_not_1(temp_path):
    dbpath = temp_path / "nodedb"

    db = sqlite3.connect(str(dbpath))
    db.execute('CREATE TABLE schema_version (version)')
    db.close()

    # there's no version information!
    with pytest.raises(BadDatabaseError):
        SQLitePeerInfo(dbpath)

    db = sqlite3.connect(str(dbpath))
    with db:
        db.execute('INSERT INTO schema_version VALUES (2)')
    db.close()

    # version 2 is not supported!
    with pytest.raises(BadDatabaseError):
        SQLitePeerInfo(dbpath)


def test_records_failures():
    # where can you get a random pubkey from?
    peer_info = MemoryPeerInfo()

    node = NodeFactory()
    assert peer_info.should_connect_to(node) is True

    peer_info.record_failure(node, HandshakeFailure())

    assert peer_info.should_connect_to(node) is False

    # And just to make sure, check that it's been saved to the db
    db = peer_info.db
    rows = db.execute('''
        SELECT * FROM bad_nodes
    ''').fetchall()
    assert len(rows) == 1
    assert rows[0]['enode'] == node.uri()


def test_memory_does_not_persist():
    node = NodeFactory()

    peer_info = MemoryPeerInfo()
    assert peer_info.should_connect_to(node) is True
    peer_info.record_failure(node, HandshakeFailure())
    assert peer_info.should_connect_to(node) is False
    peer_info.close()

    # open a second instance
    peer_info = MemoryPeerInfo()
    # the second instance has no memory of the failure
    assert peer_info.should_connect_to(node) is True


def test_sql_does_persist(temp_path):
    dbpath = temp_path / "nodedb"
    node = NodeFactory()

    peer_info = SQLitePeerInfo(dbpath)
    assert peer_info.should_connect_to(node) is True
    peer_info.record_failure(node, HandshakeFailure())
    assert peer_info.should_connect_to(node) is False
    peer_info.close()

    # open a second instance
    peer_info = SQLitePeerInfo(dbpath)
    # the second instance remembers the failure
    assert peer_info.should_connect_to(node) is False
    peer_info.close()


def test_timeout_works(monkeypatch):
    node = NodeFactory()

    current_time = datetime.datetime.utcnow()

    class patched_datetime(datetime.datetime):
        @classmethod
        def utcnow(cls):
            return current_time

    monkeypatch.setattr(datetime, 'datetime', patched_datetime)

    peer_info = MemoryPeerInfo()
    assert peer_info.should_connect_to(node) is True

    peer_info.record_failure(node, HandshakeFailure())
    assert peer_info.should_connect_to(node) is False

    current_time += datetime.timedelta(seconds=1)
    assert peer_info.should_connect_to(node) is False

    current_time += datetime.timedelta(seconds=10)
    assert peer_info.should_connect_to(node) is True


def test_fails_when_closed():
    peer_info = MemoryPeerInfo()
    peer_info.close()

    node = NodeFactory()
    with pytest.raises(persistence.ClosedException):
        peer_info.record_failure(node, HandshakeFailure())
