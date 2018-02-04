import rlp

from trie import (
    BinaryTrie,
    HexaryTrie,
)

from eth_utils import (
    keccak,
)

from evm.constants import (
    BLANK_ROOT_HASH,
    EMPTY_SHA3,
)
from evm.exceptions import (
    UnannouncedStateAccess,
)
from evm.db.immutable import (
    ImmutableDB,
)
from evm.db.tracked import (
    TrackedDB,
)
from evm.rlp.accounts import (
    Account,
)
from evm.validation import (
    validate_is_bytes,
    validate_uint256,
    validate_canonical_address,
)

from evm.utils.state_access_restriction import (
    is_accessible,
)
from evm.utils.numeric import (
    big_endian_to_int,
    int_to_big_endian,
)
from evm.utils.padding import (
    pad32,
)
from evm.utils.state_access_restriction import (
    get_code_key,
    get_balance_key,
    get_storage_key,
)

from .hash_trie import HashTrie


class BaseAccountStateDB:

    def apply_state_dict(self, state_dict):
        raise NotImplementedError("Must be implemented by subclasses")

    def decommission(self):
        raise NotImplementedError("Must be implemented by subclasses")

    @property
    def root_hash(self):
        raise NotImplementedError("Must be implemented by subclasses")

    @root_hash.setter
    def root_hash(self, value):
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Storage
    #
    def get_storage(self, address, slot):
        raise NotImplementedError("Must be implemented by subclasses")

    def set_storage(self, address, slot, value):
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Balance
    #
    def get_balance(self, address):
        raise NotImplementedError("Must be implemented by subclasses")

    def set_balance(self, address, balance):
        raise NotImplementedError("Must be implemented by subclasses")

    def delta_balance(self, address, delta):
        self.set_balance(address, self.get_balance(address) + delta)

    #
    # Code
    #
    def set_code(self, address, code):
        raise NotImplementedError("Must be implemented by subclasses")

    def get_code(self, address):
        raise NotImplementedError("Must be implemented by subclasses")

    def get_code_hash(self, address):
        raise NotImplementedError("Must be implemented by subclasses")

    def delete_code(self, address):
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Account Methods
    #
    def account_is_empty(self, address):
        raise NotImplementedError("Must be implemented by subclass")


class MainAccountStateDB(BaseAccountStateDB):

    def __init__(self, db, root_hash=BLANK_ROOT_HASH, read_only=False):
        if read_only:
            self.db = ImmutableDB(db)
        else:
            self.db = TrackedDB(db)
        self._trie = HashTrie(HexaryTrie(self.db, root_hash))

    def apply_state_dict(self, state_dict):
        for account, account_data in state_dict.items():
            self.set_balance(account, account_data["balance"])
            self.set_nonce(account, account_data["nonce"])
            self.set_code(account, account_data["code"])

            for slot, value in account_data["storage"].items():
                self.set_storage(account, slot, value)

    def decommission(self):
        self.db = None
        self._trie = None

    @property
    def root_hash(self):
        return self._trie.root_hash

    @root_hash.setter
    def root_hash(self, value):
        self._trie.root_hash = value

    #
    # Storage
    #
    def get_storage(self, address, slot):
        validate_canonical_address(address, title="Storage Address")
        validate_uint256(slot, title="Storage Slot")

        account = self._get_account(address)
        storage = HashTrie(HexaryTrie(self.db, account.storage_root))

        slot_as_key = pad32(int_to_big_endian(slot))

        if slot_as_key in storage:
            encoded_value = storage[slot_as_key]
            return rlp.decode(encoded_value, sedes=rlp.sedes.big_endian_int)
        else:
            return 0

    def set_storage(self, address, slot, value):
        validate_uint256(value, title="Storage Value")
        validate_uint256(slot, title="Storage Slot")
        validate_canonical_address(address, title="Storage Address")

        account = self._get_account(address)
        storage = HashTrie(HexaryTrie(self.db, account.storage_root))

        slot_as_key = pad32(int_to_big_endian(slot))

        if value:
            encoded_value = rlp.encode(value)
            storage[slot_as_key] = encoded_value
        else:
            del storage[slot_as_key]

        account.storage_root = storage.root_hash
        self._set_account(address, account)

    def delete_storage(self, address):
        validate_canonical_address(address, title="Storage Address")

        account = self._get_account(address)
        account.storage_root = BLANK_ROOT_HASH
        self._set_account(address, account)

    #
    # Balance
    #
    def get_balance(self, address):
        validate_canonical_address(address, title="Storage Address")

        account = self._get_account(address)
        return account.balance

    def set_balance(self, address, balance):
        validate_canonical_address(address, title="Storage Address")
        validate_uint256(balance, title="Account Balance")

        account = self._get_account(address)
        account.balance = balance
        self._set_account(address, account)

    #
    # Nonce
    #
    def set_nonce(self, address, nonce):
        validate_canonical_address(address, title="Storage Address")
        validate_uint256(nonce, title="Nonce")

        account = self._get_account(address)
        account.nonce = nonce

        self._set_account(address, account)

    def get_nonce(self, address):
        validate_canonical_address(address, title="Storage Address")

        account = self._get_account(address)
        return account.nonce

    def increment_nonce(self, address):
        current_nonce = self.get_nonce(address)
        self.set_nonce(address, current_nonce + 1)

    #
    # Code
    #
    def set_code(self, address, code):
        validate_canonical_address(address, title="Storage Address")
        validate_is_bytes(code, title="Code")

        account = self._get_account(address)

        account.code_hash = keccak(code)
        self.db[account.code_hash] = code
        self._set_account(address, account)

    def get_code(self, address):
        validate_canonical_address(address, title="Storage Address")

        try:
            return self.db[self.get_code_hash(address)]
        except KeyError:
            return b""

    def get_code_hash(self, address):
        validate_canonical_address(address, title="Storage Address")

        account = self._get_account(address)
        return account.code_hash

    def delete_code(self, address):
        validate_canonical_address(address, title="Storage Address")

        account = self._get_account(address)
        account.code_hash = EMPTY_SHA3
        self._set_account(address, account)

    #
    # Account Methods
    #
    def account_has_code_or_nonce(self, address):
        return self.get_nonce(address) != 0 or self.get_code_hash(address) != EMPTY_SHA3

    def delete_account(self, address):
        validate_canonical_address(address, title="Storage Address")

        del self._trie[address]

    def account_exists(self, address):
        validate_canonical_address(address, title="Storage Address")

        return bool(self._trie[address])

    def touch_account(self, address):
        validate_canonical_address(address, title="Storage Address")

        account = self._get_account(address)
        self._set_account(address, account)

    def account_is_empty(self, address):
        return not self.account_has_code_or_nonce(address) and self.get_balance(address) == 0

    #
    # Internal
    #
    def _get_account(self, address):
        rlp_account = self._trie[address]
        if rlp_account:
            account = rlp.decode(rlp_account, sedes=Account)
            account._mutable = True
        else:
            account = Account()
        return account

    def _set_account(self, address, account):
        self._trie[address] = rlp.encode(account, sedes=Account)


class ShardingAccountStateDB(BaseAccountStateDB):

    def __init__(self, db, root_hash=EMPTY_SHA3, read_only=False, access_list=None):
        if read_only:
            self.db = ImmutableDB(db)
        else:
            self.db = TrackedDB(db)
        self._trie = BinaryTrie(self.db, root_hash)
        self.is_access_restricted = access_list is not None
        self.access_list = access_list

    def apply_state_dict(self, state_dict):
        for account, account_data in state_dict.items():
            self.set_balance(account, account_data["balance"])
            self.set_code(account, account_data["code"])

            for slot, value in account_data["storage"].items():
                self.set_storage(account, slot, value)

    def decommission(self):
        self._trie = None

    @property
    def root_hash(self):
        return self._trie.root_hash

    @root_hash.setter
    def root_hash(self, value):
        self._trie.root_hash = value

    #
    # Storage
    #
    def get_storage(self, address, slot):
        validate_canonical_address(address, title="Storage Address")
        validate_uint256(slot, title="Storage Slot")

        key = get_storage_key(address, slot)
        self._check_accessibility(key)

        if key in self._trie:
            return big_endian_to_int(self._trie[key])
        else:
            return 0

    def set_storage(self, address, slot, value):
        validate_uint256(value, title="Storage Value")
        validate_uint256(slot, title="Storage Slot")
        validate_canonical_address(address, title="Storage Address")

        key = get_storage_key(address, slot)
        self._check_accessibility(key)

        if value:
            self._trie[key] = int_to_big_endian(value)
        else:
            del self._trie[key]

    #
    # Balance
    #
    def get_balance(self, address):
        validate_canonical_address(address, title="Storage Address")

        key = get_balance_key(address)
        self._check_accessibility(key)

        if key in self._trie:
            return big_endian_to_int(self._trie[key])
        else:
            return 0

    def set_balance(self, address, balance):
        validate_canonical_address(address, title="Storage Address")
        validate_uint256(balance, title="Account Balance")

        key = get_balance_key(address)
        self._check_accessibility(key)

        self._trie[key] = int_to_big_endian(balance)

    #
    # Code
    #
    def get_code(self, address):
        validate_canonical_address(address, title="Storage Address")

        key = get_code_key(address)
        self._check_accessibility(key)

        if key in self._trie:
            return self._trie[key]
        else:
            return b""

    def get_code_hash(self, address):
        code = self.get_code(address)
        return keccak(code)

    def set_code(self, address, code):
        validate_canonical_address(address, title="Storage Address")
        validate_is_bytes(code, title="Code")

        key = get_code_key(address)
        self._check_accessibility(key)

        self._trie[key] = code

    def delete_code(self, address):
        validate_canonical_address(address, title="Storage Address")

        key = get_code_key(address)
        self._check_accessibility(key)

        del self._trie[key]

    def account_has_code(self, address):
        code = self.get_code(address)
        return bool(code)

    #
    # Account Methods
    #
    def account_is_empty(self, address):
        return not self.account_has_code(address) and self.get_balance(address) == 0

    #
    # Internal
    #
    def _check_accessibility(self, key):
        if self.is_access_restricted:
            if not is_accessible(key, self.access_list):
                raise UnannouncedStateAccess("Attempted state access outside of access set")
