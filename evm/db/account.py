from abc import (
    ABCMeta,
    abstractmethod
)
from uuid import UUID

from lru import LRU

import rlp

from trie import (
    HexaryTrie,
)

from eth_utils import (
    keccak,
)

from evm.constants import (
    BLANK_ROOT_HASH,
    EMPTY_SHA3,
)
from evm.db.immutable import (
    ImmutableDB,
)
from evm.exceptions import DecommissionedAccountDB
from evm.rlp.accounts import (
    Account,
)
from evm.validation import (
    validate_is_bytes,
    validate_uint256,
    validate_canonical_address,
)

from evm.utils.numeric import (
    int_to_big_endian,
)
from evm.utils.padding import (
    pad32,
)

from .hash_trie import HashTrie


# Use lru-dict instead of functools.lru_cache because the latter doesn't let us invalidate a single
# entry, so we'd have to invalidate the whole cache in _set_account() and that turns out to be too
# expensive.
account_cache = LRU(2048)


class BaseAccountDB(metaclass=ABCMeta):

    @abstractmethod
    def __init__(self) -> None:
        raise NotImplementedError(
            "Must be implemented by subclasses"
        )

    @abstractmethod
    def apply_state_dict(self, state_dict):
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    def decommission(self):
        raise NotImplementedError("Must be implemented by subclasses")

    # We need to ignore this until https://github.com/python/mypy/issues/4165 is resolved
    @property  # type: ignore
    @abstractmethod
    def root_hash(self):
        raise NotImplementedError("Must be implemented by subclasses")

    @root_hash.setter  # type: ignore
    @abstractmethod
    def root_hash(self, value):
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Storage
    #
    @abstractmethod
    def get_storage(self, address, slot):
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    def set_storage(self, address, slot, value):
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Balance
    #
    @abstractmethod
    def get_balance(self, address):
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    def set_balance(self, address, balance):
        raise NotImplementedError("Must be implemented by subclasses")

    def delta_balance(self, address, delta):
        self.set_balance(address, self.get_balance(address) + delta)

    #
    # Code
    #
    @abstractmethod
    def set_code(self, address, code):
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    def get_code(self, address):
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    def get_code_hash(self, address):
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    def delete_code(self, address):
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Account Methods
    #
    @abstractmethod
    def account_is_empty(self, address):
        raise NotImplementedError("Must be implemented by subclass")

    #
    # Record and discard API
    #
    @abstractmethod
    def record(self) -> UUID:
        raise NotImplementedError("Must be implemented by subclass")

    @abstractmethod
    def discard(self, checkpoint: UUID) -> None:
        raise NotImplementedError("Must be implemented by subclass")

    @abstractmethod
    def commit(self, checkpoint: UUID) -> None:
        raise NotImplementedError("Must be implemented by subclass")

    @abstractmethod
    def clear(self) -> None:
        raise NotImplementedError("Must be implemented by subclass")


class AccountDB(BaseAccountDB):

    def __init__(self, db, root_hash=BLANK_ROOT_HASH, read_only=False):
        # Keep a reference to the original db instance to use it as part of _get_account()'s cache
        # key.
        self._unwrapped_db = db
        if read_only:
            self.db = ImmutableDB(db)
        else:
            self.db = db
        self.__trie = HashTrie(HexaryTrie(self.db, root_hash))

    @property
    def _trie(self):
        if self.__trie is None:
            raise DecommissionedAccountDB()
        return self.__trie

    @_trie.setter
    def _trie(self, value):
        self.__trie = value

    def apply_state_dict(self, state_dict):
        for account, account_data in state_dict.items():
            self.set_balance(account, account_data["balance"])
            self.set_nonce(account, account_data["nonce"])
            self.set_code(account, account_data["code"])

            for slot, value in account_data["storage"].items():
                self.set_storage(account, slot, value)

    def decommission(self):
        self.db = None
        self.__trie = None

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

        self._set_account(address, account.copy(storage_root=storage.root_hash))

    def delete_storage(self, address):
        validate_canonical_address(address, title="Storage Address")

        account = self._get_account(address)
        self._set_account(address, account.copy(storage_root=BLANK_ROOT_HASH))

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
        self._set_account(address, account.copy(balance=balance))

    #
    # Nonce
    #
    def get_nonce(self, address):
        validate_canonical_address(address, title="Storage Address")

        account = self._get_account(address)
        return account.nonce

    def set_nonce(self, address, nonce):
        validate_canonical_address(address, title="Storage Address")
        validate_uint256(nonce, title="Nonce")

        account = self._get_account(address)
        self._set_account(address, account.copy(nonce=nonce))

    def increment_nonce(self, address):
        current_nonce = self.get_nonce(address)
        self.set_nonce(address, current_nonce + 1)

    #
    # Code
    #
    def get_code(self, address):
        validate_canonical_address(address, title="Storage Address")

        try:
            return self.db[self.get_code_hash(address)]
        except KeyError:
            return b""

    def set_code(self, address, code):
        validate_canonical_address(address, title="Storage Address")
        validate_is_bytes(code, title="Code")

        account = self._get_account(address)

        code_hash = keccak(code)
        self.db[code_hash] = code
        self._set_account(address, account.copy(code_hash=code_hash))

    def get_code_hash(self, address):
        validate_canonical_address(address, title="Storage Address")

        account = self._get_account(address)
        return account.code_hash

    def delete_code(self, address):
        validate_canonical_address(address, title="Storage Address")

        account = self._get_account(address)
        self._set_account(address, account.copy(code_hash=EMPTY_SHA3))

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
        cache_key = (self._unwrapped_db, self.root_hash, address)
        if cache_key not in account_cache:
            account_cache[cache_key] = self._trie[address]

        rlp_account = account_cache[cache_key]
        if rlp_account:
            account = rlp.decode(rlp_account, sedes=Account)
        else:
            account = Account()
        return account

    def _set_account(self, address, account):
        rlp_account = rlp.encode(account, sedes=Account)
        self._trie[address] = rlp_account
        cache_key = (self._unwrapped_db, self.root_hash, address)
        account_cache[cache_key] = rlp_account

    #
    # Record and discard API
    #
    def record(self) -> UUID:
        return self._unwrapped_db.record()

    def discard(self, changeset_id: UUID) -> None:
        self._unwrapped_db.discard(changeset_id)

    def commit(self, changeset_id: UUID) -> None:
        self._unwrapped_db.commit(changeset_id)

    def persist(self) -> None:
        self._unwrapped_db.persist()

    def clear(self) -> None:
        self._unwrapped_db.reset()

    def exists(self, key: bytes) -> bool:
        return self._unwrapped_db.exists(key)
