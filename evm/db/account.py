from abc import (
    ABCMeta,
    abstractmethod
)
from uuid import UUID
import logging
from lru import LRU
from typing import Set, Tuple  # noqa: F401

from eth_typing import Hash32

import rlp

from trie import (
    HexaryTrie,
)

from eth_hash.auto import keccak
from eth_utils import encode_hex

from evm.constants import (
    BLANK_ROOT_HASH,
    EMPTY_SHA3,
)
from evm.db.batch import (
    BatchDB,
)
from evm.db.cache import (
    CacheDB,
)
from evm.db.journal import (
    JournalDB,
)
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

    # We need to ignore this until https://github.com/python/mypy/issues/4165 is resolved
    @property  # tyoe: ignore
    @abstractmethod
    def state_root(self):
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    def has_root(self, state_root: bytes) -> bool:
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

    logger = logging.getLogger('evm.db.account.AccountDB')

    def __init__(self, db, state_root=BLANK_ROOT_HASH):
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

    @property
    def state_root(self):
        return self._trie.root_hash

    @state_root.setter
    def state_root(self, value):
        self._trie_cache.reset_cache()
        self._trie.root_hash = value

    def has_root(self, state_root: bytes) -> bool:
        return state_root in self._batchtrie

    #
    # Storage
    #
    def get_storage(self, address, slot):
        validate_canonical_address(address, title="Storage Address")
        validate_uint256(slot, title="Storage Slot")

        account = self._get_account(address)
        storage = HashTrie(HexaryTrie(self._journaldb, account.storage_root))

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
        storage = HashTrie(HexaryTrie(self._journaldb, account.storage_root))

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
            return self._journaldb[self.get_code_hash(address)]
        except KeyError:
            return b""

    def set_code(self, address, code):
        validate_canonical_address(address, title="Storage Address")
        validate_is_bytes(code, title="Code")

        account = self._get_account(address)

        code_hash = keccak(code)
        self._journaldb[code_hash] = code
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

        del self._journaltrie[address]

    def account_exists(self, address):
        validate_canonical_address(address, title="Storage Address")

        return self._journaltrie.get(address, b'') != b''

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
        rlp_account = self._journaltrie.get(address, b'')
        if rlp_account:
            account = rlp.decode(rlp_account, sedes=Account)
        else:
            account = Account()
        return account

    def _set_account(self, address, account):
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

    def commit(self, changeset: Tuple[UUID, UUID]) -> None:
        db_changeset, trie_changeset = changeset
        self._journaldb.commit(db_changeset)
        self._journaltrie.commit(trie_changeset)

    def make_state_root(self) -> Hash32:
        self.logger.debug("Generating AccountDB trie")
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
        for checkpoint, accounts in reversed(queued_changes):  # type: ignore
            for address in accounts:
                if address in accounts_displayed:
                    continue
                else:
                    accounts_displayed.add(address)
                    account = self._get_account(address)
                    self.logger.debug(
                        "Account %s: balance %d, nonce %d, storage root %s, code hash %s",
                        encode_hex(address),
                        account.balance,
                        account.nonce,
                        encode_hex(account.storage_root),
                        encode_hex(account.code_hash),
                    )
