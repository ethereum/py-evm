from abc import (
    ABC,
    abstractmethod
)
from uuid import UUID
import logging
from lru import LRU
from typing import cast, Set, Tuple  # noqa: F401

from eth_typing import (
    Address,
    Hash32
)

import rlp

from trie import (
    HexaryTrie,
)

from eth_hash.auto import keccak
from eth_utils import (
    encode_hex,
    int_to_big_endian,
)

from eth.constants import (
    BLANK_ROOT_HASH,
    EMPTY_SHA3,
)
from eth.db.backends.base import (
    BaseDB,
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
from eth.rlp.accounts import (
    Account,
)
from eth.validation import (
    validate_is_bytes,
    validate_uint256,
    validate_canonical_address,
)
from eth.tools.logging import (
    ExtendedDebugLogger
)
from eth._utils.padding import (
    pad32,
)

from .hash_trie import HashTrie


class BaseAccountDB(ABC):

    @abstractmethod
    def __init__(self) -> None:
        raise NotImplementedError(
            "Must be implemented by subclasses"
        )

    @property
    @abstractmethod
    def state_root(self) -> Hash32:
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    def has_root(self, state_root: bytes) -> bool:
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Storage
    #
    @abstractmethod
    def get_storage(self, address: Address, slot: int) -> int:
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    def set_storage(self, address: Address, slot: int, value: int) -> None:
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Nonce
    #
    @abstractmethod
    def get_nonce(self, address: Address) -> int:
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    def set_nonce(self, address: Address, nonce: int) -> None:
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Balance
    #
    @abstractmethod
    def get_balance(self, address: Address) -> int:
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    def set_balance(self, address: Address, balance: int) -> None:
        raise NotImplementedError("Must be implemented by subclasses")

    def delta_balance(self, address: Address, delta: int) -> None:
        self.set_balance(address, self.get_balance(address) + delta)

    #
    # Code
    #
    @abstractmethod
    def set_code(self, address: Address, code: bytes) -> None:
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    def get_code(self, address: Address) -> bytes:
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    def get_code_hash(self, address: Address) -> Hash32:
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    def delete_code(self, address: Address) -> None:
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Account Methods
    #
    @abstractmethod
    def account_is_empty(self, address: Address) -> bool:
        raise NotImplementedError("Must be implemented by subclass")

    #
    # Record and discard API
    #
    @abstractmethod
    def record(self) -> Tuple[UUID, UUID]:
        raise NotImplementedError("Must be implemented by subclass")

    @abstractmethod
    def discard(self, changeset: Tuple[UUID, UUID]) -> None:
        raise NotImplementedError("Must be implemented by subclass")

    @abstractmethod
    def commit(self, changeset: Tuple[UUID, UUID]) -> None:
        raise NotImplementedError("Must be implemented by subclass")

    @abstractmethod
    def make_state_root(self) -> Hash32:
        """
        Generate the state root with all the current changes in AccountDB

        :return: the new state root
        """
        raise NotImplementedError("Must be implemented by subclass")

    @abstractmethod
    def persist(self) -> None:
        """
        Send changes to underlying database, including the trie state
        so that it will forever be possible to read the trie from this checkpoint.
        """
        raise NotImplementedError("Must be implemented by subclass")


class AccountDB(BaseAccountDB):

    logger = cast(ExtendedDebugLogger, logging.getLogger('eth.db.account.AccountDB'))

    def __init__(self, db: BaseDB, state_root: Hash32=BLANK_ROOT_HASH) -> None:
        r"""
        Internal implementation details (subject to rapid change):
        Database entries go through several pipes, like so...

        .. code::

                                                                    -> hash-trie -> storage lookups
                                                                  /
            db > _batchdb ---------------------------> _journaldb ----------------> code lookups
             \
              -> _batchtrie -> _trie -> _trie_cache -> _journaltrie --------------> account lookups

        Journaling sequesters writes at the _journal* attrs ^, until persist is called.

        _batchtrie enables us to prune all trie changes while building
        state,  without deleting old trie roots.

        _batchdb and _batchtrie together enable us to make the state root,
        without saving everything to the database.

        _journaldb is a journaling of the keys and values used to store
        code and account storage.

        _trie is a hash-trie, used to generate the state root

        _trie_cache is a cache tied to the state root of the trie. It
        is important that this cache is checked *after* looking for
        the key in _journaltrie, because the cache is only invalidated
        after a state root change.

        _journaltrie is a journaling of the accounts (an address->rlp mapping,
        rather than the nodes stored by the trie). This enables
        a squashing of all account changes before pushing them into the trie.

        .. NOTE:: There is an opportunity to do something similar for storage

        AccountDB synchronizes the snapshot/revert/persist of both of the
        journals.
        """
        self._batchdb = BatchDB(db)
        self._batchtrie = BatchDB(db)
        self._journaldb = JournalDB(self._batchdb)
        self._trie = HashTrie(HexaryTrie(self._batchtrie, state_root, prune=True))
        self._trie_cache = CacheDB(self._trie)
        self._journaltrie = JournalDB(self._trie_cache)
        self._account_cache = LRU(2048)

    @property
    def state_root(self) -> Hash32:
        return self._trie.root_hash

    @state_root.setter
    def state_root(self, value: Hash32) -> None:
        self._trie_cache.reset_cache()
        self._trie.root_hash = value

    def has_root(self, state_root: bytes) -> bool:
        return state_root in self._batchtrie

    #
    # Storage
    #
    def get_storage(self, address: Address, slot: int, from_journal: bool=True) -> int:
        validate_canonical_address(address, title="Storage Address")
        validate_uint256(slot, title="Storage Slot")

        account = self._get_account(address, from_journal)
        storage = HashTrie(HexaryTrie(self._journaldb, account.storage_root))

        slot_as_key = pad32(int_to_big_endian(slot))

        if slot_as_key in storage:
            encoded_value = storage[slot_as_key]
            return rlp.decode(encoded_value, sedes=rlp.sedes.big_endian_int)
        else:
            return 0

    def set_storage(self, address: Address, slot: int, value: int) -> None:
        validate_uint256(value, title="Storage Value")
        validate_uint256(slot, title="Storage Slot")
        validate_canonical_address(address, title="Storage Address")

        account = self._get_account(address)
        storage = HashTrie(HexaryTrie(self._journaldb, account.storage_root))

        slot_as_key = pad32(int_to_big_endian(slot))

        if value:
            encoded_value = rlp.encode(value)
            storage[slot_as_key] = encoded_value
        else:
            del storage[slot_as_key]

        self._set_account(address, account.copy(storage_root=storage.root_hash))

    def delete_storage(self, address: Address) -> None:
        validate_canonical_address(address, title="Storage Address")

        account = self._get_account(address)
        self._set_account(address, account.copy(storage_root=BLANK_ROOT_HASH))

    #
    # Balance
    #
    def get_balance(self, address: Address) -> int:
        validate_canonical_address(address, title="Storage Address")

        account = self._get_account(address)
        return account.balance

    def set_balance(self, address: Address, balance: int) -> None:
        validate_canonical_address(address, title="Storage Address")
        validate_uint256(balance, title="Account Balance")

        account = self._get_account(address)
        self._set_account(address, account.copy(balance=balance))

    #
    # Nonce
    #
    def get_nonce(self, address: Address) -> int:
        validate_canonical_address(address, title="Storage Address")

        account = self._get_account(address)
        return account.nonce

    def set_nonce(self, address: Address, nonce: int) -> None:
        validate_canonical_address(address, title="Storage Address")
        validate_uint256(nonce, title="Nonce")

        account = self._get_account(address)
        self._set_account(address, account.copy(nonce=nonce))

    def increment_nonce(self, address: Address) -> None:
        current_nonce = self.get_nonce(address)
        self.set_nonce(address, current_nonce + 1)

    #
    # Code
    #
    def get_code(self, address: Address) -> bytes:
        validate_canonical_address(address, title="Storage Address")

        try:
            return self._journaldb[self.get_code_hash(address)]
        except KeyError:
            return b""

    def set_code(self, address: Address, code: bytes) -> None:
        validate_canonical_address(address, title="Storage Address")
        validate_is_bytes(code, title="Code")

        account = self._get_account(address)

        code_hash = keccak(code)
        self._journaldb[code_hash] = code
        self._set_account(address, account.copy(code_hash=code_hash))

    def get_code_hash(self, address: Address) -> Hash32:
        validate_canonical_address(address, title="Storage Address")

        account = self._get_account(address)
        return account.code_hash

    def delete_code(self, address: Address) -> None:
        validate_canonical_address(address, title="Storage Address")

        account = self._get_account(address)
        self._set_account(address, account.copy(code_hash=EMPTY_SHA3))

    #
    # Account Methods
    #
    def account_has_code_or_nonce(self, address: Address) -> bool:
        return self.get_nonce(address) != 0 or self.get_code_hash(address) != EMPTY_SHA3

    def delete_account(self, address: Address) -> None:
        validate_canonical_address(address, title="Storage Address")
        if address in self._account_cache:
            del self._account_cache[address]
        del self._journaltrie[address]

    def account_exists(self, address: Address) -> bool:
        validate_canonical_address(address, title="Storage Address")
        return self._journaltrie.get(address, b'') != b''

    def touch_account(self, address: Address) -> None:
        validate_canonical_address(address, title="Storage Address")

        account = self._get_account(address)
        self._set_account(address, account)

    def account_is_empty(self, address: Address) -> bool:
        return not self.account_has_code_or_nonce(address) and self.get_balance(address) == 0

    #
    # Internal
    #
    def _get_account(self, address: Address, from_journal: bool=True) -> Account:
        if from_journal and address in self._account_cache:
            return self._account_cache[address]
        rlp_account = (self._journaltrie if from_journal else self._trie_cache).get(address, b'')
        if rlp_account:
            account = rlp.decode(rlp_account, sedes=Account)
        else:
            account = Account()
        if from_journal:
            self._account_cache[address] = account
        return account

    def _set_account(self, address: Address, account: Account) -> None:
        self._account_cache[address] = account
        rlp_account = rlp.encode(account, sedes=Account)
        self._journaltrie[address] = rlp_account

    #
    # Record and discard API
    #
    def record(self) -> Tuple[UUID, UUID]:
        return (self._journaldb.record(), self._journaltrie.record())

    def discard(self, changeset: Tuple[UUID, UUID]) -> None:
        db_changeset, trie_changeset = changeset
        self._journaldb.discard(db_changeset)
        self._journaltrie.discard(trie_changeset)
        self._account_cache.clear()

    def commit(self, changeset: Tuple[UUID, UUID]) -> None:
        db_changeset, trie_changeset = changeset
        self._journaldb.commit(db_changeset)
        self._journaltrie.commit(trie_changeset)

    def make_state_root(self) -> Hash32:
        self.logger.debug2("Generating AccountDB trie")
        self._journaldb.persist()
        self._journaltrie.persist()
        return self.state_root

    def persist(self) -> None:
        self.make_state_root()
        self._batchtrie.commit(apply_deletes=False)
        self._batchdb.commit(apply_deletes=True)

    def _log_pending_accounts(self) -> None:
        accounts_displayed = set()  # type: Set[bytes]
        queued_changes = self._journaltrie.journal.journal_data.items()
        # mypy bug for ordered dict reversibility: https://github.com/python/typeshed/issues/2078
        for _, accounts in reversed(queued_changes):
            for address in accounts:
                if address in accounts_displayed:
                    continue
                else:
                    accounts_displayed.add(address)
                    account = self._get_account(Address(address))
                    self.logger.debug2(
                        "Account %s: balance %d, nonce %d, storage root %s, code hash %s",
                        encode_hex(address),
                        account.balance,
                        account.nonce,
                        encode_hex(account.storage_root),
                        encode_hex(account.code_hash),
                    )
