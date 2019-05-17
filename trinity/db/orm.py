from pathlib import Path

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import (
    OperationalError,
)
from sqlalchemy.orm.exc import (
    NoResultFound,
    MultipleResultsFound,
)
from sqlalchemy.orm import (
    sessionmaker,
    Session as BaseSession,
)
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
)

from trinity.exceptions import (
    BadDatabaseError,
)


Base = declarative_base()


SCHEMA_VERSION = '3'


class SchemaVersion(Base):
    __tablename__ = 'schema_version'

    id = Column(Integer, primary_key=True)
    version = Column(String, unique=True, nullable=False, index=True)


#
# SQL Based Trackers
#
def _get_session(path: Path) -> BaseSession:
    # python 3.6 does not support sqlite3.connect(Path)
    is_memory = path.name == ':memory:'

    if is_memory:
        database_uri = 'sqlite:///:memory:'
    else:
        database_uri = f'sqlite:///{path.resolve()}'

    engine = create_engine(database_uri)
    Session = sessionmaker(bind=engine)
    session = Session()
    return session


def _setup_schema(session: BaseSession) -> None:
    Base.metadata.create_all(session.get_bind())
    session.add(SchemaVersion(version=SCHEMA_VERSION))
    # mypy doesn't know about the type of the `commit()` function
    session.commit()  # type: ignore


def _check_is_empty(session: BaseSession) -> bool:
    engine = session.get_bind()
    for table_name in Base.metadata.tables.keys():
        if engine.has_table(table_name):
            return False
    return True


def _check_schema_version(session: BaseSession) -> bool:
    if not session.get_bind().has_table(SchemaVersion.__tablename__):
        return False

    try:
        # mypy doesn't know about the type of the `query()` function
        schema_version = session.query(SchemaVersion).one()  # type: ignore
    except NoResultFound:
        return False
    except MultipleResultsFound:
        return False
    except OperationalError:
        # table is present but schema doesn't match query
        return False
    else:
        return schema_version.version == SCHEMA_VERSION


def _check_tables_exist(session: BaseSession) -> bool:
    engine = session.get_bind()
    for table_name in Base.metadata.tables.keys():
        if not engine.has_table(table_name):
            return False
    return True


def get_tracking_database(db_path: Path) -> BaseSession:
    session = _get_session(db_path)

    if _check_is_empty(session):
        _setup_schema(session)
        return session
    elif not _check_schema_version(session) or not _check_tables_exist(session):
        raise BadDatabaseError(
            f"Tracking database has incorrect schema: {db_path.resolve()}."
            "This can normally be fixed by clearing your network database "
            "with the CLI command `trinity remove-network-db`"
        )

    return session
