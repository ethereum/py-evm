import pytest

from eth.db.atomic import AtomicDB
from eth.db.backends.level import LevelDB

from eth.tools.db.base import DatabaseAPITestSuite
from eth.tools.db.atomic import AtomicDatabaseBatchAPITestSuite


@pytest.fixture(params=['atomic', 'level'])
def atomic_db(request, tmpdir):
    if request.param == 'atomic':
        return AtomicDB()
    elif request.param == 'level':
        return LevelDB(db_path=tmpdir.mkdir("level_db_path"))
    else:
        raise ValueError(f"Unexpected database type: {request.param}")


@pytest.fixture
def db(atomic_db):
    return atomic_db


class TestAtomicDatabaseBatchAPI(AtomicDatabaseBatchAPITestSuite):
    pass


class TestAtomicDatabaseAPI(DatabaseAPITestSuite):
    pass
