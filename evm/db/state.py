import logging

import rlp

from trie import (
    HexaryTrie
)

from evm.constants import (
    BLANK_ROOT_HASH,
    EMPTY_SHA3,
    BALANCE_TRIE_PREFIX,
    CODE_TRIE_PREFIX,
    NONCE_TRIE_PREFIX,
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
from evm.utils.keccak import (
    keccak,
)
from evm.utils.numeric import (
    int_to_big_endian,
)
from evm.utils.padding import (
    pad32,
)

from .hash_trie import HashTrie
from .backends.base import BaseDB


class AccountStateDB:
    """
    High level API around account storage.
    """
    db = None
    _trie = None

    logger = logging.getLogger('evm.state.State')

    def __init__(
        self,
        db,
        root_hash=BLANK_ROOT_HASH,
        read_only=False,
        read_list=None,
        write_list=None
    ):
        if read_only:
            self.db = TrackedDB(ImmutableDB(db))
        else:
            self.db = TrackedDB(db)
        self._trie = HashTrie(HexaryTrie(self.db, root_hash))

        self.check_access_restrictions = read_list is not None or write_list is not None
        self.read_list = read_list
        self.write_list = write_list

    #
    # Base API
    #
    @property
    def root_hash(self):
        return self._trie.root_hash

    @root_hash.setter
    def root_hash(self, value):
        self._trie.root_hash = value

    def set_storage(self, address, slot, value):
        validate_uint256(value, title="Storage Value")
        validate_uint256(slot, title="Storage Slot")
        validate_canonical_address(address, title="Storage Address")

        slot_as_key = pad32(int_to_big_endian(slot))

        if self.check_access_restrictions:
            if not is_accessible(address, slot_as_key, self.write_list):
                raise UnannouncedStateAccess(
                    "Attempted writing to storage slot outside of write list"
                )

        account = self._get_account(address)
        storage = HashTrie(HexaryTrie(self.db, account.storage_root))

        if value:
            encoded_value = rlp.encode(value)
            storage[slot_as_key] = encoded_value
        else:
            del storage[slot_as_key]

        account.storage_root = storage.root_hash
        self._set_account(address, account)

    def get_storage(self, address, slot):
        validate_canonical_address(address, title="Storage Address")
        validate_uint256(slot, title="Storage Slot")

        slot_as_key = pad32(int_to_big_endian(slot))

        if self.check_access_restrictions:
            if not is_accessible(address, slot_as_key, self.read_list):
                raise UnannouncedStateAccess(
                    "Attempted reading from storage slot outside of read list"
                )

        account = self._get_account(address)
        storage = HashTrie(HexaryTrie(self.db, account.storage_root))

        if slot_as_key in storage:
            encoded_value = storage[slot_as_key]
            return rlp.decode(encoded_value, sedes=rlp.sedes.big_endian_int)
        else:
            return 0

    def delete_storage(self, address):
        validate_canonical_address(address, title="Storage Address")

        if self.check_access_restrictions:
            if not is_accessible(address, b'', self.write_list):
                raise UnannouncedStateAccess(
                    "Attempted writing to storage slot outside of write list"
                )

        account = self._get_account(address)
        account.storage_root = BLANK_ROOT_HASH
        self._set_account(address, account)

    def set_balance(self, address, balance):
        validate_canonical_address(address, title="Storage Address")
        validate_uint256(balance, title="Account Balance")

        if self.check_access_restrictions:
            if keccak(address) + BALANCE_TRIE_PREFIX not in self.write_list:
                # TODO: use is_accessible once two layer trie is implemented
                raise UnannouncedStateAccess(
                    "Attempted setting balance of account outside of write list"
                )

        account = self._get_account(address)
        account.balance = balance

        self._set_account(address, account)

    def delta_balance(self, address, delta):
        self.set_balance(address, self.get_balance(address) + delta)

    def get_balance(self, address):
        validate_canonical_address(address, title="Storage Address")

        if self.check_access_restrictions:
            # TODO: use is_accessible once two layer trie is implemented
            if keccak(address) + BALANCE_TRIE_PREFIX not in self.read_list:
                raise UnannouncedStateAccess(
                    "Attempted reading balance of account outside of read list"
                )

        account = self._get_account(address)
        return account.balance

    def set_nonce(self, address, nonce):
        validate_canonical_address(address, title="Storage Address")
        validate_uint256(nonce, title="Nonce")

        if self.check_access_restrictions:
            # TODO: use is_accessible once two layer trie is implemented
            if keccak(address) + NONCE_TRIE_PREFIX not in self.write_list:
                raise UnannouncedStateAccess(
                    "Attempted setting nonce of account outside of write list"
                )

        account = self._get_account(address)
        account.nonce = nonce

        self._set_account(address, account)

    def get_nonce(self, address):
        validate_canonical_address(address, title="Storage Address")

        if self.check_access_restrictions:
            # TODO: use is_accessible once two layer trie is implemented
            if keccak(address) + NONCE_TRIE_PREFIX not in self.read_list:
                raise UnannouncedStateAccess(
                    "Attempted reading nonce of account outside of read list"
                )

        account = self._get_account(address)
        return account.nonce

    def set_code(self, address, code):
        validate_canonical_address(address, title="Storage Address")
        validate_is_bytes(code, title="Code")

        if self.check_access_restrictions:
            # TODO: use is_accessible once two layer trie is implemented
            if keccak(address) + CODE_TRIE_PREFIX not in self.write_list:
                raise UnannouncedStateAccess(
                    "Attempted setting code of account outside of write list"
                )

        account = self._get_account(address)

        account.code_hash = keccak(code)
        self.db[account.code_hash] = code
        self._set_account(address, account)

    def get_code(self, address):
        try:
            return self.db[self.get_code_hash(address)]
        except KeyError:
            return b''

    def get_code_hash(self, address):
        validate_canonical_address(address, title="Storage Address")

        if self.check_access_restrictions:
            # TODO: use is_accessible once two layer trie is implemented
            if keccak(address) + CODE_TRIE_PREFIX not in self.read_list:
                raise UnannouncedStateAccess(
                    "Attempted reading code hash of account outside of read list"
                )

        account = self._get_account(address)
        return account.code_hash

    def delete_code(self, address):
        validate_canonical_address(address, title="Storage Address")

        if self.check_access_restrictions:
            # TODO: use is_accessible once two layer trie is implemented
            if keccak(address) + CODE_TRIE_PREFIX not in self.write_list:
                raise UnannouncedStateAccess(
                    "Attempted setting code of account outside of write list"
                )

        account = self._get_account(address)
        account.code_hash = EMPTY_SHA3
        self._set_account(address, account)

    #
    # Account Methods
    #
    def delete_account(self, address):
        # TODO: check access restriction?
        del self._trie[address]

    def account_exists(self, address):
        # TODO: check access restriction?
        validate_canonical_address(address, title="Storage Address")
        return bool(self._trie[address])

    def account_has_code_or_nonce(self, address):
        # TODO: check access restriction?
        if not self.account_exists(address):
            return False
        account = self._get_account(address)
        if account.nonce != 0:
            return True
        elif account.code_hash != EMPTY_SHA3:
            return True
        else:
            return False

    def account_is_empty(self, address):
        # TODO: check access restriction?
        validate_canonical_address(address, title="Storage Address")
        account = self._get_account(address)
        if account.code_hash != EMPTY_SHA3:
            return False
        elif account.balance != 0:
            return False
        elif account.nonce != 0:
            return False
        else:
            return True

    def touch_account(self, address):
        account = self._get_account(address)
        self._set_account(address, account)

    def increment_nonce(self, address):
        current_nonce = self.get_nonce(address)
        self.set_nonce(address, current_nonce + 1)

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


class StateDB(BaseDB):
    """
    The StateDB would be responsible for collecting all the touched keys.

    reads: the dict of read key-value
    writes: the dict of written key-value
    """

    wrapped_db = None
    _reads = None
    _writes = None

    def __init__(self, db):
        self.wrapped_db = db
        self._reads = {}
        self._writes = {}

    def get(self, key):
        """
        Return the value of specific key and update read dict.
        """
        try:
            current_value = self.wrapped_db.get(key)
        except KeyError:
            raise
        else:
            self._reads[key] = current_value

        return current_value

    def set(self, key, value):
        """
        Set the key-value and update writes dict.
        """
        self._writes[key] = value
        return self.wrapped_db.set(key, value)

    def exists(self, key):
        """
        Check if the key exsits.
        """
        return self.wrapped_db.exists(key)

    def delete(self, key):
        """
        Delete the key and update writes dict.
        """
        try:
            current_value = self.wrapped_db.get(key)
        except KeyError:
            # do not need to be added in writes
            pass
        else:
            self._writes[key] = current_value

        return self.wrapped_db.delete(key)

    def get_reads(self, key=None):
        """
        Return the whole or the specific value of reads dict.
        """
        if key is None:
            return self._reads
        else:
            return self._reads[key] if key in self._reads else None

    def get_writes(self, key=None):
        """
        Return the whole or the specific value of writes dict.
        """
        if key is None:
            return self._writes
        else:
            return self._writes[key] if key in self._writes else None

    def clear_log(self):
        """
        Clear reads and writes dicts.
        """
        self._reads = {}
        self._writes = {}
