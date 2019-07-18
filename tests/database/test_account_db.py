import pytest

from eth_hash.auto import keccak

from eth_utils import (
    ValidationError,
)

from eth.db.atomic import AtomicDB
from eth.db.backends.memory import MemoryDB
from eth.db.account import (
    AccountDB,
)

from eth.constants import (
    EMPTY_SHA3,
)


ADDRESS = b'\xaa' * 20
OTHER_ADDRESS = b'\xbb' * 20
INVALID_ADDRESS = b'aa' * 20


@pytest.fixture
def base_db():
    return AtomicDB()


@pytest.fixture
def account_db(base_db):
    return AccountDB(base_db)


@pytest.mark.parametrize("state", [
    AccountDB(MemoryDB()),
])
def test_balance(state):
    assert state.get_balance(ADDRESS) == 0

    state.set_balance(ADDRESS, 1)
    assert state.get_balance(ADDRESS) == 1
    assert state.get_balance(OTHER_ADDRESS) == 0

    with pytest.raises(ValidationError):
        state.get_balance(INVALID_ADDRESS)
    with pytest.raises(ValidationError):
        state.set_balance(INVALID_ADDRESS, 1)
    with pytest.raises(ValidationError):
        state.set_balance(ADDRESS, 1.0)


@pytest.mark.parametrize("state", [
    AccountDB(MemoryDB()),
])
def test_nonce(state):
    assert state.get_nonce(ADDRESS) == 0

    state.set_nonce(ADDRESS, 5)
    assert state.get_nonce(ADDRESS) == 5
    assert state.get_nonce(OTHER_ADDRESS) == 0

    state.increment_nonce(ADDRESS)
    assert state.get_nonce(ADDRESS) == 6
    assert state.get_nonce(OTHER_ADDRESS) == 0

    with pytest.raises(ValidationError):
        state.get_nonce(INVALID_ADDRESS)
    with pytest.raises(ValidationError):
        state.set_nonce(INVALID_ADDRESS, 1)
    with pytest.raises(ValidationError):
        state.increment_nonce(INVALID_ADDRESS)
    with pytest.raises(ValidationError):
        state.set_nonce(ADDRESS, 1.0)


@pytest.mark.parametrize("state", [
    AccountDB(MemoryDB()),
])
def test_code(state):
    assert state.get_code(ADDRESS) == b''
    assert state.get_code_hash(ADDRESS) == EMPTY_SHA3

    state.set_code(ADDRESS, b'code')
    assert state.get_code(ADDRESS) == b'code'
    assert state.get_code(OTHER_ADDRESS) == b''
    assert state.get_code_hash(ADDRESS) == keccak(b'code')

    with pytest.raises(ValidationError):
        state.get_code(INVALID_ADDRESS)
    with pytest.raises(ValidationError):
        state.set_code(INVALID_ADDRESS, b'code')
    with pytest.raises(ValidationError):
        state.set_code(ADDRESS, 'code')


@pytest.mark.parametrize("state", [
    AccountDB(MemoryDB()),
])
def test_accounts(state):
    assert not state.account_exists(ADDRESS)
    assert not state.account_has_code_or_nonce(ADDRESS)

    state.touch_account(ADDRESS)
    assert state.account_exists(ADDRESS)
    assert state.get_nonce(ADDRESS) == 0
    assert state.get_balance(ADDRESS) == 0
    assert state.get_code(ADDRESS) == b''

    assert not state.account_has_code_or_nonce(ADDRESS)
    state.increment_nonce(ADDRESS)
    assert state.account_has_code_or_nonce(ADDRESS)

    state.delete_account(ADDRESS)
    assert not state.account_exists(ADDRESS)
    assert not state.account_has_code_or_nonce(ADDRESS)

    with pytest.raises(ValidationError):
        state.account_exists(INVALID_ADDRESS)
    with pytest.raises(ValidationError):
        state.delete_account(INVALID_ADDRESS)
    with pytest.raises(ValidationError):
        state.account_has_code_or_nonce(INVALID_ADDRESS)


def test_storage(account_db):
    assert account_db.get_storage(ADDRESS, 0) == 0

    account_db.set_storage(ADDRESS, 0, 123)
    assert account_db.get_storage(ADDRESS, 0) == 123
    assert account_db.get_storage(ADDRESS, 1) == 0
    assert account_db.get_storage(OTHER_ADDRESS, 0) == 0


def test_storage_deletion(account_db):
    account_db.set_storage(ADDRESS, 0, 123)
    account_db.set_storage(OTHER_ADDRESS, 1, 321)
    account_db.delete_storage(ADDRESS)
    assert account_db.get_storage(ADDRESS, 0) == 0
    assert account_db.get_storage(OTHER_ADDRESS, 1) == 321


def test_account_db_storage_root(account_db):
    """
    Make sure that pruning doesn't screw up addresses that temporarily share storage roots
    """
    account_db.set_storage(ADDRESS, 1, 2)
    account_db.set_storage(OTHER_ADDRESS, 1, 2)

    # both addresses will share the same root
    account_db.make_state_root()

    account_db.set_storage(ADDRESS, 3, 4)
    account_db.set_storage(OTHER_ADDRESS, 3, 5)

    # addresses will have different roots
    account_db.make_state_root()

    assert account_db.get_storage(ADDRESS, 1) == 2
    assert account_db.get_storage(OTHER_ADDRESS, 1) == 2
    assert account_db.get_storage(ADDRESS, 3) == 4
    assert account_db.get_storage(OTHER_ADDRESS, 3) == 5

    account_db.persist()

    assert account_db.get_storage(ADDRESS, 1) == 2
    assert account_db.get_storage(OTHER_ADDRESS, 1) == 2
    assert account_db.get_storage(ADDRESS, 3) == 4
    assert account_db.get_storage(OTHER_ADDRESS, 3) == 5


def test_account_db_update_then_make_root_then_read(account_db):
    assert account_db.get_storage(ADDRESS, 1) == 0
    account_db.set_storage(ADDRESS, 1, 2)
    assert account_db.get_storage(ADDRESS, 1) == 2

    account_db.make_state_root()

    assert account_db.get_storage(ADDRESS, 1) == 2

    account_db.persist()
    assert account_db.get_storage(ADDRESS, 1) == 2


def test_account_db_read_then_update_then_make_root_then_read(account_db):
    account_db.set_storage(ADDRESS, 1, 2)

    # must always explicitly make the root before persisting
    account_db.make_state_root()
    account_db.persist()

    # read out of a non-empty account, to build a read-cache trie
    assert account_db.get_storage(ADDRESS, 1) == 2

    account_db.set_storage(ADDRESS, 1, 3)

    assert account_db.get_storage(ADDRESS, 1) == 3

    account_db.make_state_root()

    assert account_db.get_storage(ADDRESS, 1) == 3

    account_db.persist()
    # if you start caching read tries, then you might get this answer wrong:
    assert account_db.get_storage(ADDRESS, 1) == 3
