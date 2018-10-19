import multiprocessing
import random

import pytest

from eth.db.backends.rocks import RocksDB

from trinity.utils.ipc import kill_process_gracefully


@pytest.fixture
def db_path(tmpdir):
    return tmpdir.mkdir("rocks_db_path")


@pytest.fixture
def db(db_path):
    return RocksDB(db_path=db_path)


DB_DATA = {
    b'key-%r' % i: b'value-%r' % i
    for i in range(1024)
}


def seed_database(db):
    for key, value in DB_DATA.items():
        db[key] = value


def do_random_reads(db_path):
    db = RocksDB(db_path=db_path, read_only=True)
    for _ in range(1024):
        idx = random.randint(0, 1023)
        key = b'key-%r' % idx
        expected = b'value-%r' % idx
        value = db[key]
        assert value == expected


def test_database_read_access_across_multiple_processes(db, db_path):
    seed_database(db)

    proc_a = multiprocessing.Process(target=do_random_reads, kwargs={'db_path': db_path})
    proc_b = multiprocessing.Process(target=do_random_reads, kwargs={'db_path': db_path})

    proc_a.start()
    proc_b.start()

    try:
        proc_a.join(2)
        proc_b.join(2)
    finally:
        kill_process_gracefully(proc_a)
        kill_process_gracefully(proc_b)

    assert proc_a.exitcode is 0
    assert proc_b.exitcode is 0


def test_database_read_access_across_multiple_processes_with_ongoing_writes(db, db_path):
    seed_database(db)

    data_to_write = {
        b'key-%r' % i: b'value-%r' % i
        for i in range(1024, 4096)
    }

    proc_a = multiprocessing.Process(target=do_random_reads, kwargs={'db_path': db_path})
    proc_b = multiprocessing.Process(target=do_random_reads, kwargs={'db_path': db_path})

    proc_a.start()
    proc_b.start()

    for key, value in data_to_write.items():
        db[key] = value

    try:
        proc_a.join(2)
        proc_b.join(2)
    finally:
        kill_process_gracefully(proc_a)
        kill_process_gracefully(proc_b)

    assert proc_a.exitcode is 0
    assert proc_b.exitcode is 0

    for key, value in data_to_write.items():
        assert db[key] == value
