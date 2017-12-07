import pytest
from evm.db.backends.memory import MemoryDB
from evm.db.state import StateDB


@pytest.fixture
def state_db():
    return StateDB(MemoryDB())


def test_set_and_get(state_db):
    state_db.set(b'1', b'test')
    assert state_db.get_writes(b'1') == b'test'

    assert state_db.get(b'1') == b'test'
    assert state_db.get_reads(b'1') == b'test'


def test_exists_and_clear_log_and_delete(state_db):
    state_db.set(b'1', b'test')
    assert state_db.get_writes(b'1') == b'test'

    # exists
    assert state_db.exists(b'1')

    # clear writes
    assert state_db.get_writes(b'1') == b'test'
    state_db.clear_log()
    assert state_db.get_writes(b'1') is None
    assert not state_db.get_writes()
    assert not state_db.get_reads()

    # delete
    state_db.delete(b'1')
    assert state_db.get_writes(b'1') == b'test'


def test_get_non_existent_value(state_db):
    with pytest.raises(KeyError):
        state_db.get(b'does-not-exist')
    assert b'does-not-exist' not in state_db.get_reads()


def test_delete_non_existent_value(state_db):
    with pytest.raises(KeyError):
        state_db.delete(b'does-not-exist')
    assert b'does-not-exist' not in state_db.get_writes()
