from abc import ABC, abstractmethod
from collections import namedtuple
import datetime
import functools
from pathlib import Path
import sqlite3
from typing import Any, Callable, TypeVar, cast, Dict, Type, Optional

from trinity._utils.logging import HasExtendedDebugLogger

from p2p.kademlia import Node
from p2p.exceptions import (
    BadDatabaseError,
    BaseP2PError,
    HandshakeFailure,
    TooManyPeersFailure,
    WrongNetworkFailure,
    WrongGenesisFailure,
)


BadNode = namedtuple('BadNode', ['enode', 'until', 'reason', 'error_count'])


ONE_DAY = 60 * 60 * 24
FAILURE_TIMEOUTS: Dict[Type[Exception], int] = {
    HandshakeFailure: 10,  # 10 seconds
    WrongNetworkFailure: ONE_DAY,
    WrongGenesisFailure: ONE_DAY,
    TooManyPeersFailure: 60,  # one minute
}


def timeout_for_failure(failure: BaseP2PError) -> int:
    for cls in type(failure).__mro__:
        if cls in FAILURE_TIMEOUTS:
            return FAILURE_TIMEOUTS[cls]
    failure_name = type(failure).__name__
    raise Exception(f'Unknown failure type: {failure_name}')


def time_to_str(time: datetime.datetime) -> str:
    return time.isoformat(timespec='seconds')


def str_to_time(as_str: str) -> datetime.datetime:
    # use datetime.datetime.fromisoformat once support for 3.6 is dropped
    return datetime.datetime.strptime(as_str, "%Y-%m-%dT%H:%M:%S")


def utc_to_local(utc: datetime.datetime) -> datetime.datetime:
    local_tz = datetime.datetime.now().astimezone()
    return utc + local_tz.utcoffset()


class BasePeerInfo(ABC, HasExtendedDebugLogger):
    @abstractmethod
    def record_failure(self, remote: Node, failure: BaseP2PError) -> None:
        pass

    @abstractmethod
    def should_connect_to(self, remote: Node) -> bool:
        pass


class NoopPeerInfo(BasePeerInfo):
    def record_failure(self, remote: Node, failure: BaseP2PError) -> None:
        pass

    def should_connect_to(self, remote: Node) -> bool:
        return True


class ClosedException(Exception):
    'This should never happen, this represents a logic error somewhere in the code'
    pass


T = TypeVar('T', bound=Callable[..., Any])


def must_be_open(func: T) -> T:
    @functools.wraps(func)
    def wrapper(self: 'SQLitePeerInfo', *args: Any, **kwargs: Any) -> Any:
        if self.closed:
            msg = "SQLitePeerInfo cannot be used after it's been closed"
            raise ClosedException(msg)
        return func(self, *args, **kwargs)
    return cast(T, wrapper)


class SQLitePeerInfo(BasePeerInfo):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.closed = False

        # python 3.6 does not support sqlite3.connect(Path)
        self.db = sqlite3.connect(str(self.path))
        self.db.row_factory = sqlite3.Row
        self.setup_schema()

    def __str__(self) -> str:
        return f'<SQLitePeerInfo({self.path})>'

    @must_be_open
    def record_failure(self, remote: Node, failure: BaseP2PError) -> None:
        failure_name = type(failure).__name__
        timeout = timeout_for_failure(failure)

        self._record_bad_node(
            remote,
            timeout=timeout,  # one minute
            reason=failure_name
        )

    @must_be_open
    def _record_bad_node(self, remote: Node, timeout: int, reason: str) -> None:
        enode = remote.uri()
        bad_node = self._fetch_bad_node(remote)
        now = datetime.datetime.utcnow()
        if bad_node:
            new_error_count = bad_node.error_count + 1
            usable_time = now + datetime.timedelta(seconds=timeout * new_error_count)
            local_time = utc_to_local(usable_time)
            self.logger.debug(
                '%s will not be retried until %s because %s', remote, local_time, reason
            )
            self._update_bad_node(enode, usable_time, reason, new_error_count)
            return

        usable_time = now + datetime.timedelta(seconds=timeout)
        local_time = utc_to_local(usable_time)
        self.logger.debug(
            '%s will not be retried until %s because %s', remote, local_time, reason
        )
        self._insert_bad_node(enode, usable_time, reason, error_count=1)

    @must_be_open
    def should_connect_to(self, remote: Node) -> bool:
        bad_node = self._fetch_bad_node(remote)

        if not bad_node:
            return True

        until = str_to_time(bad_node.until)
        if datetime.datetime.utcnow() < until:
            local_time = utc_to_local(until)
            self.logger.debug(
                'skipping %s, it failed because "%s" and is not usable until %s',
                remote, bad_node.reason, local_time
            )
            return False

        return True

    def _fetch_bad_node(self, remote: Node) -> Optional[BadNode]:
        enode = remote.uri()
        cursor = self.db.execute('SELECT * from bad_nodes WHERE enode = ?', (enode,))
        row = cursor.fetchone()
        if not row:
            return None
        result = BadNode(row['enode'], row['until'], row['reason'], row['error_count'])
        return result

    def _insert_bad_node(self,
                         enode: str,
                         until: datetime.datetime,
                         reason: str,
                         error_count: int) -> None:
        with self.db:
            self.db.execute(
                '''
                INSERT INTO bad_nodes (enode, until, reason, error_count)
                VALUES (?, ?, ?, ?)
                ''',
                (enode, time_to_str(until), reason, error_count),
            )

    def _update_bad_node(self,
                         enode: str,
                         until: datetime.datetime,
                         reason: str,
                         error_count: int) -> None:
        with self.db:
            self.db.execute(
                '''
                UPDATE bad_nodes
                SET until = ?, reason = ?, error_count = ?
                WHERE enode = ?
                ''',
                (time_to_str(until), reason, error_count, enode),
            )

    def close(self) -> None:
        self.db.close()
        self.db = None
        self.closed = True

    @must_be_open
    def setup_schema(self) -> None:
        try:
            if self._schema_already_created():
                return
        except Exception:
            self.close()
            raise

        with self.db:
            self.db.execute('create table bad_nodes (enode, until, reason, error_count)')
            self.db.execute('create table schema_version (version)')
            self.db.execute('insert into schema_version VALUES (1)')

    def _schema_already_created(self) -> bool:
        "Inspects the database to see if the expected tables already exist"

        count = self.db.execute("""
            SELECT count() FROM sqlite_master
            WHERE type='table' AND name='schema_version'
        """).fetchone()['count()']
        if count == 0:
            return False

        # a schema_version table already exists, get the version
        cur = self.db.execute("SELECT version FROM schema_version")
        rows = cur.fetchall()
        if len(rows) != 1:
            self.logger.error(
                "malformed nodedb. try deleting %s. (got rows: %s)",
                self.path, rows,
            )
            raise BadDatabaseError(
                "malformed nodedb: Expected one row in schema_version and got %s",
                len(rows),
            )
        version = rows[0]['version']
        if version != 1:
            # in the future this block might kick off a schema migration
            self.logger.error("malformed. try deleting %s", self.path)
            raise BadDatabaseError(
                "cannot read nodedb: version %s is unsupported", version
            )

        # schema_version exists and is 1, this database has already been initialized!
        return True


class MemoryPeerInfo(SQLitePeerInfo):
    def __init__(self) -> None:
        super().__init__(Path(":memory:"))

    def __str__(self) -> str:
        return '<MemoryPeerInfo()>'
