import pytest

import copy

from eth_utils import (
    keccak,
)

from evm.exceptions import (
    UnannouncedStateAccess,
    ValidationError,
)

from evm.db.backends.memory import MemoryDB
from evm.db.state import (
    MainAccountStateDB,
    ShardingAccountStateDB,
)

from evm.constants import (
    EMPTY_SHA3,
)
from evm.utils.state_access_restriction import (
    get_balance_key,
    get_code_key,
    get_storage_key,
)


ADDRESS = b'\xaa' * 20
OTHER_ADDRESS = b'\xbb' * 20
INVALID_ADDRESS = b'aa' * 20


@pytest.mark.parametrize("state", [
    MainAccountStateDB(MemoryDB()),
    ShardingAccountStateDB(MemoryDB()),
])
def test_balance(state):
    assert state.get_balance(ADDRESS) == 0

    state.set_balance(ADDRESS, 1)
    assert state.get_balance(ADDRESS) == 1
    assert state.get_balance(OTHER_ADDRESS) == 0

    state.delta_balance(ADDRESS, 2)
    assert state.get_balance(ADDRESS) == 3
    assert state.get_balance(OTHER_ADDRESS) == 0

    with pytest.raises(ValidationError):
        state.get_balance(INVALID_ADDRESS)
    with pytest.raises(ValidationError):
        state.set_balance(INVALID_ADDRESS, 1)
    with pytest.raises(ValidationError):
        state.delta_balance(INVALID_ADDRESS, 1)
    with pytest.raises(ValidationError):
        state.set_balance(ADDRESS, 1.0)
    with pytest.raises(ValidationError):
        state.delta_balance(ADDRESS, 1.0)


@pytest.mark.parametrize("state", [
    MainAccountStateDB(MemoryDB()),
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
    MainAccountStateDB(MemoryDB()),
    ShardingAccountStateDB(MemoryDB()),
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
    ShardingAccountStateDB(MemoryDB()),
])
def test_has_code(state):
    assert not state.account_has_code(ADDRESS)
    state.set_code(ADDRESS, b"")
    assert not state.account_has_code(ADDRESS)
    state.set_code(ADDRESS, b"code")
    assert state.account_has_code(ADDRESS)
    state.set_code(ADDRESS, b"")
    assert not state.account_has_code(ADDRESS)


@pytest.mark.parametrize("state", [
    MainAccountStateDB(MemoryDB()),
    ShardingAccountStateDB(MemoryDB()),
])
def test_storage(state):
    assert state.get_storage(ADDRESS, 0) == 0

    state.set_storage(ADDRESS, 0, 123)
    assert state.get_storage(ADDRESS, 0) == 123
    assert state.get_storage(ADDRESS, 1) == 0
    assert state.get_storage(OTHER_ADDRESS, 0) == 0

    with pytest.raises(ValidationError):
        state.get_storage(INVALID_ADDRESS, 0)
    with pytest.raises(ValidationError):
        state.set_storage(INVALID_ADDRESS, 0, 0)
    with pytest.raises(ValidationError):
        state.get_storage(ADDRESS, b'\x00')
    with pytest.raises(ValidationError):
        state.set_storage(ADDRESS, b'\x00', 0)
    with pytest.raises(ValidationError):
        state.set_storage(ADDRESS, 0, b'asdf')


@pytest.mark.parametrize("state", [
    MainAccountStateDB(MemoryDB()),
])
def test_storage_deletion(state):
    state.set_storage(ADDRESS, 0, 123)
    state.set_storage(OTHER_ADDRESS, 1, 321)
    state.delete_storage(ADDRESS)
    assert state.get_storage(ADDRESS, 0) == 0
    assert state.get_storage(OTHER_ADDRESS, 1) == 321

    with pytest.raises(ValidationError):
        state.delete_storage(INVALID_ADDRESS)


@pytest.mark.parametrize("state", [
    MainAccountStateDB(MemoryDB()),
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


def test_access_restriction():
    # populate db
    state = ShardingAccountStateDB(MemoryDB())
    state.set_balance(ADDRESS, 2)
    state.set_code(ADDRESS, b"code")
    state.set_storage(ADDRESS, 123, 4)

    original_db = state.db
    original_root_hash = state.root_hash

    def make_state(access_list):
        kv_store = copy.deepcopy(original_db.wrapped_db.kv_store)
        db = MemoryDB(kv_store)
        return ShardingAccountStateDB(db, original_root_hash, access_list=access_list)

    # access lists to use
    CODE_ACCESS_LIST = [get_code_key(ADDRESS)]
    BALANCE_ACCESS_LIST = [get_balance_key(ADDRESS)]
    STORAGE_ACCESS_LIST = [get_storage_key(ADDRESS, 123)]

    # test with access list
    state = make_state(BALANCE_ACCESS_LIST)
    state.get_balance(ADDRESS)
    state.set_balance(ADDRESS, 3)
    state.delta_balance(ADDRESS, 1)

    state = make_state(CODE_ACCESS_LIST)
    state.get_code(ADDRESS)
    state.set_code(ADDRESS, b"new_code")

    state = make_state(STORAGE_ACCESS_LIST)
    state.get_storage(ADDRESS, 123)
    state.set_storage(ADDRESS, 123, 5)

    # test without access list
    state = make_state([])
    with pytest.raises(UnannouncedStateAccess):
        state.get_balance(ADDRESS)
    with pytest.raises(UnannouncedStateAccess):
        state.set_balance(ADDRESS, 3)
    with pytest.raises(UnannouncedStateAccess):
        state.delta_balance(ADDRESS, 1)

    with pytest.raises(UnannouncedStateAccess):
        state.get_code(ADDRESS)
    with pytest.raises(UnannouncedStateAccess):
        state.set_code(ADDRESS, b"new_code")

    with pytest.raises(UnannouncedStateAccess):
        state.get_storage(ADDRESS, 123)
    with pytest.raises(UnannouncedStateAccess):
        state.set_storage(ADDRESS, 123, 5)
