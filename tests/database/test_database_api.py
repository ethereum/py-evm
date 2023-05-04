import pytest

from eth.db.accesslog import (
    KeyAccessLoggerAtomicDB,
    KeyAccessLoggerDB,
)
from eth.db.atomic import (
    AtomicDB,
)
from eth.db.backends.memory import (
    MemoryDB,
)
from eth.db.batch import (
    BatchDB,
)
from eth.db.cache import (
    CacheDB,
)
from eth.db.journal import (
    JournalDB,
)
from eth.tools.db.base import (
    DatabaseAPITestSuite,
)


@pytest.fixture(
    params=[
        JournalDB,
        BatchDB,
        MemoryDB,
        AtomicDB,
        CacheDB,
        KeyAccessLoggerAtomicDB,
        KeyAccessLoggerDB,
    ]
)
def db(request):
    base_db = MemoryDB()
    if request.param is JournalDB:
        yield JournalDB(base_db)
    elif request.param is BatchDB:
        yield BatchDB(base_db)
    elif request.param is MemoryDB:
        yield base_db
    elif request.param is AtomicDB:
        atomic_db = AtomicDB(base_db)
        with atomic_db.atomic_batch() as batch:
            yield batch
    elif request.param is CacheDB:
        yield CacheDB(base_db)
    elif request.param is KeyAccessLoggerAtomicDB:
        atomic_db = AtomicDB(base_db)
        yield KeyAccessLoggerAtomicDB(atomic_db)
    elif request.param is KeyAccessLoggerDB:
        yield KeyAccessLoggerDB(base_db)
    else:
        raise Exception("Invariant")


class TestDatabaseAPI(DatabaseAPITestSuite):
    pass
