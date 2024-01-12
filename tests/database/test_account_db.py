from eth_hash.auto import (
    keccak,
)
from eth_utils import (
    ValidationError,
)
import pytest

from eth.constants import (
    EMPTY_SHA3,
)
from eth.db.account import (
    AccountDB,
)
from eth.db.atomic import (
    AtomicDB,
)
from eth.db.backends.memory import (
    MemoryDB,
)

ADDRESS = b"\xaa" * 20
OTHER_ADDRESS = b"\xbb" * 20
INVALID_ADDRESS = b"aa" * 20


@pytest.fixture
def base_db():
    return AtomicDB()


@pytest.fixture
def account_db(base_db):
    return AccountDB(base_db)


@pytest.mark.parametrize(
    "state",
    [
        AccountDB(MemoryDB()),
    ],
)
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


@pytest.mark.parametrize(
    "state",
    [
        AccountDB(MemoryDB()),
    ],
)
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


@pytest.mark.parametrize(
    "state",
    [
        AccountDB(MemoryDB()),
    ],
)
def test_code(state):
    assert state.get_code(ADDRESS) == b""
    assert state.get_code_hash(ADDRESS) == EMPTY_SHA3

    state.set_code(ADDRESS, b"code")
    assert state.get_code(ADDRESS) == b"code"
    assert state.get_code(OTHER_ADDRESS) == b""
    assert state.get_code_hash(ADDRESS) == keccak(b"code")

    with pytest.raises(ValidationError):
        state.get_code(INVALID_ADDRESS)
    with pytest.raises(ValidationError):
        state.set_code(INVALID_ADDRESS, b"code")
    with pytest.raises(ValidationError):
        state.set_code(ADDRESS, "code")


@pytest.mark.parametrize(
    "state",
    [
        AccountDB(MemoryDB()),
    ],
)
def test_accounts(state):
    assert not state.account_exists(ADDRESS)
    assert not state.account_has_code_or_nonce(ADDRESS)

    state.touch_account(ADDRESS)
    assert state.account_exists(ADDRESS)
    assert state.get_nonce(ADDRESS) == 0
    assert state.get_balance(ADDRESS) == 0
    assert state.get_code(ADDRESS) == b""

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
    Make sure that pruning doesn't screw up addresses
    that temporarily share storage roots
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


def test_has_changes_even_if_storage_root_returns_to_old_value(account_db):
    account_db.set_storage(ADDRESS, 1, 2)

    # must always explicitly make the root before persisting
    account_db.make_state_root()
    storage_db = account_db._get_address_store(ADDRESS)

    # changed root only shows up after making root
    assert storage_db.has_changed_root
    original_storage_root = storage_db.get_changed_root()

    account_db.persist()
    assert not storage_db.has_changed_root

    account_db.set_storage(ADDRESS, 1, 3)

    account_db.lock_changes()
    account_db.make_state_root()

    storage_db = account_db._get_address_store(ADDRESS)
    assert storage_db.has_changed_root
    assert storage_db.get_changed_root() != original_storage_root

    # change storage
    account_db.set_storage(ADDRESS, 1, 2)

    account_db.lock_changes()
    account_db.make_state_root()

    # even after the storage root changes back to the original root,
    # it should be marked as changed
    storage_db = account_db._get_address_store(ADDRESS)
    assert storage_db.has_changed_root

    repeated_storage_root = storage_db.get_changed_root()
    assert repeated_storage_root == original_storage_root


def test_meta_witness_basic_stats(account_db):
    account_db.get_balance(ADDRESS)
    account_db.get_code(ADDRESS)
    account_db.set_storage(OTHER_ADDRESS, 1, 321)
    THIRD_ADDRESS = b"c" * 20
    account_db.set_code(THIRD_ADDRESS, b"fake")
    account_db.get_code(THIRD_ADDRESS)

    meta_witness = account_db.persist()

    # addresses were accessed
    assert ADDRESS in meta_witness.accounts_queried
    assert OTHER_ADDRESS in meta_witness.accounts_queried
    assert THIRD_ADDRESS in meta_witness.accounts_queried

    # note that although code was accessed, it was empty, so is not considered accessed,
    #   because the empty hash is well-known
    assert ADDRESS not in meta_witness.account_bytecodes_queried
    assert meta_witness.get_slots_queried(ADDRESS) == frozenset()

    # setting storage data alone does not require reading storage data,
    #   so a set does not count as a read! (Although in practice, the
    #   EVM essentially always reads before setting (except for the special
    #   case of self-destruct).
    assert OTHER_ADDRESS not in meta_witness.account_bytecodes_queried
    assert meta_witness.get_slots_queried(OTHER_ADDRESS) == frozenset()

    # note that although code was accessed, it was created during execution,
    #   so it doesn't need to be listed in the witness index
    assert THIRD_ADDRESS not in meta_witness.account_bytecodes_queried
    assert meta_witness.get_slots_queried(THIRD_ADDRESS) == frozenset()


def test_meta_witness_reset_stats_empty(account_db):
    # Do a variety of accesses that should not show up in the second
    #   persist() result.
    account_db.get_balance(ADDRESS)
    account_db.get_code(ADDRESS)
    account_db.set_storage(OTHER_ADDRESS, 1, 321)
    THIRD_ADDRESS = b"c" * 20
    account_db.set_code(THIRD_ADDRESS, b"fake")
    account_db.get_code(THIRD_ADDRESS)

    # When returning this witness index, the results are emptied
    meta_witness = account_db.persist()

    # Note that a new witness from a new persist call should always be empty
    meta_witness = account_db.persist()
    assert len(meta_witness.hashes) == 0
    assert len(meta_witness.accounts_queried) == 0


def test_meta_witness_reset_stats_refilled(account_db):
    # Do a variety of accesses that should not show up in the second
    #   persist() result.
    account_db.set_storage(OTHER_ADDRESS, 1, 321)
    THIRD_ADDRESS = b"c" * 20
    account_db.set_code(THIRD_ADDRESS, b"fake")

    # When returning this witness index, the results are emptied
    account_db.persist()

    # Only these accesses should show up in the next witness index
    account_db.get_storage(OTHER_ADDRESS, 2)
    account_db.get_code(THIRD_ADDRESS)

    meta_witness = account_db.persist()

    # addresses were accessed
    assert OTHER_ADDRESS in meta_witness.accounts_queried
    assert THIRD_ADDRESS in meta_witness.accounts_queried
    # this address was not accessed this round
    assert ADDRESS not in meta_witness.accounts_queried

    # New storage slot accessed, no code access
    assert OTHER_ADDRESS not in meta_witness.account_bytecodes_queried
    assert meta_witness.get_slots_queried(OTHER_ADDRESS) == frozenset({2})

    # Since code was accessed this round, and not created this round,
    #   the code for this account must be listed in the witness
    assert THIRD_ADDRESS in meta_witness.account_bytecodes_queried
    assert meta_witness.get_slots_queried(THIRD_ADDRESS) == frozenset()
