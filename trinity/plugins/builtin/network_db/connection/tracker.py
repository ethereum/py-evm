import datetime
import math
from pathlib import Path

from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    String,
)
from sqlalchemy.orm import (
    Session as BaseSession,
)
from sqlalchemy.orm.exc import (
    NoResultFound,
)

from lahja import (
    AsyncioEndpoint,
    BroadcastConfig,
)

from eth_utils import humanize_seconds

from p2p.kademlia import Node
from p2p.tracking.connection import BaseConnectionTracker

from trinity.constants import (
    NETWORKDB_EVENTBUS_ENDPOINT,
)

from trinity.db.orm import (
    Base,
    get_tracking_database,
)
from .events import (
    BlacklistEvent,
    ShouldConnectToPeerRequest,
)


class BlacklistRecord(Base):
    __tablename__ = 'blacklist_records'

    id = Column(Integer, primary_key=True)
    uri = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    reason = Column(String, nullable=False)
    error_count = Column(Integer, default=1, nullable=False)


def adjust_repeat_offender_timeout(base_timeout: float, error_count: int) -> datetime.datetime:
    """
    sub-linear scaling based on number of errors recorded against the offender.
    """
    adjusted_timeout_seconds = int(base_timeout * math.sqrt(error_count + 1))
    delta = datetime.timedelta(seconds=adjusted_timeout_seconds)
    return datetime.datetime.utcnow() + delta


class SQLiteConnectionTracker(BaseConnectionTracker):
    def __init__(self, session: BaseSession):
        self.session = session

    #
    # Core API
    #
    def record_blacklist(self, remote: Node, timeout_seconds: int, reason: str) -> None:
        try:
            record = self._get_record(remote.uri())
        except NoResultFound:
            expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=timeout_seconds)
            self._create_record(remote, expires_at, reason)
        else:
            scaled_expires_at = adjust_repeat_offender_timeout(
                timeout_seconds,
                record.error_count + 1,
            )
            self._update_record(remote, scaled_expires_at, reason)

    async def should_connect_to(self, remote: Node) -> bool:
        try:
            record = self._get_record(remote.uri())
        except NoResultFound:
            return True

        now = datetime.datetime.utcnow()
        if now < record.expires_at:
            delta = record.expires_at - now
            self.logger.debug(
                'skipping %s, it failed because "%s" and is not usable for %s',
                remote,
                record.reason,
                humanize_seconds(delta.total_seconds()),
            )
            return False

        return True

    #
    # Helpers
    #
    def _get_record(self, uri: str) -> BlacklistRecord:
        # mypy doesn't know about the type of the `commit()` function
        return self.session.query(BlacklistRecord).filter_by(uri=uri).one()  # type: ignore

    def _record_exists(self, uri: str) -> bool:
        try:
            self._get_record(uri)
        except NoResultFound:
            return False
        else:
            return True

    def _create_record(self, remote: Node, expires_at: datetime.datetime, reason: str) -> None:
        uri = remote.uri()

        record = BlacklistRecord(uri=uri, expires_at=expires_at, reason=reason)
        self.session.add(record)
        # mypy doesn't know about the type of the `commit()` function
        self.session.commit()  # type: ignore

        usable_delta = expires_at - datetime.datetime.utcnow()
        self.logger.debug(
            '%s will not be retried for %s because %s',
            remote,
            humanize_seconds(usable_delta.total_seconds()),
            reason,
        )

    def _update_record(self, remote: Node, expires_at: datetime.datetime, reason: str) -> None:
        uri = remote.uri()
        record = self._get_record(uri)

        if expires_at > record.expires_at:
            # only update expiration if it is further in the future than the existing expiration
            record.expires_at = expires_at
        record.reason = reason
        record.error_count += 1

        self.session.add(record)
        # mypy doesn't know about the type of the `commit()` function
        self.session.commit()  # type: ignore

        usable_delta = expires_at - datetime.datetime.utcnow()
        self.logger.debug(
            '%s will not be retried for %s because %s',
            remote,
            humanize_seconds(usable_delta.total_seconds()),
            reason,
        )


class MemoryConnectionTracker(SQLiteConnectionTracker):
    def __init__(self) -> None:
        session = get_tracking_database(Path(":memory:"))
        super().__init__(session)


TO_NETWORKDB_BROADCAST_CONFIG = BroadcastConfig(filter_endpoint=NETWORKDB_EVENTBUS_ENDPOINT)


class ConnectionTrackerClient(BaseConnectionTracker):
    def __init__(self,
                 event_bus: AsyncioEndpoint,
                 config: BroadcastConfig = TO_NETWORKDB_BROADCAST_CONFIG) -> None:
        self.event_bus = event_bus
        self.config = config

    def record_blacklist(self, remote: Node, timeout_seconds: int, reason: str) -> None:
        self.event_bus.broadcast_nowait(
            BlacklistEvent(remote, timeout_seconds, reason=reason),
            self.config,
        )

    async def should_connect_to(self, remote: Node) -> bool:
        response = await self.event_bus.request(
            ShouldConnectToPeerRequest(remote),
            self.config
        )
        return response.should_connect
