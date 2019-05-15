import logging
from typing import (  # noqa: F401
    cast,
    Dict,
    Iterable,
    Set,
    Tuple,
)

from eth_hash.auto import keccak
from eth_typing import (
    Address,
    Hash32
)
from eth_utils import (
    ValidationError,
    int_to_big_endian,
)
import rlp
from trie import (
    HexaryTrie,
    exceptions as trie_exceptions,
)

from eth._utils.padding import (
    pad32,
)
from eth.db.backends.base import (
    BaseAtomicDB,
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
from eth.db.typing import (
    JournalDBCheckpoint,
)
from eth.vm.interrupt import (
    MissingStorageTrieNode,
)
from eth.tools.logging import (
    ExtendedDebugLogger
)


class StorageLookup(BaseDB):
    """
    This lookup converts lookups of storage slot integers into the appropriate trie lookup.
    Similarly, it persists changes to the appropriate trie at write time.

    StorageLookup also tracks the state roots changed since the last persist.
    """
    logger = cast(ExtendedDebugLogger, logging.getLogger("eth.db.storage.StorageLookup"))

    def __init__(self, db: BaseDB, storage_root: Hash32, address: Address) -> None:
        self._db = db
        self._starting_root_hash = storage_root
        self._address = address
        self._write_trie = None
        self._trie_nodes_batch = None  # type: BatchDB

    def _get_write_trie(self) -> HexaryTrie:
        if self._trie_nodes_batch is None:
            self._trie_nodes_batch = BatchDB(self._db, read_through_deletes=True)

        if self._write_trie is None:
            batch_db = self._trie_nodes_batch
            self._write_trie = HexaryTrie(batch_db, root_hash=self._starting_root_hash, prune=True)

        return self._write_trie

    def _get_read_trie(self) -> HexaryTrie:
        if self._write_trie is not None:
            return self._write_trie
        else:
            # Creating "HexaryTrie" is a pretty light operation, so not a huge cost
            # to create a new one at every read, but we could
            # cache the read trie, if this becomes a bottleneck.
            return HexaryTrie(self._db, root_hash=self._starting_root_hash)

    def _decode_key(self, key: bytes) -> bytes:
        padded_slot = pad32(key)
        return keccak(padded_slot)

    def __getitem__(self, key: bytes) -> bytes:
        hashed_slot = self._decode_key(key)
        read_trie = self._get_read_trie()
        try:
            return read_trie[hashed_slot]
        except trie_exceptions.MissingTrieNode as exc:
            raise MissingStorageTrieNode(
                exc.missing_node_hash,
                self._starting_root_hash,
                exc.requested_key,
                self._address,
            ) from exc

    def __setitem__(self, key: bytes, value: bytes) -> None:
        hashed_slot = self._decode_key(key)
        write_trie = self._get_write_trie()
        write_trie[hashed_slot] = value

    def _exists(self, key: bytes) -> bool:
        # used by BaseDB for __contains__ checks
        hashed_slot = self._decode_key(key)
        read_trie = self._get_read_trie()
        return hashed_slot in read_trie

    def __delitem__(self, key: bytes) -> None:
        hashed_slot = self._decode_key(key)
        write_trie = self._get_write_trie()
        try:
            del write_trie[hashed_slot]
        except trie_exceptions.MissingTrieNode as exc:
            raise MissingStorageTrieNode(
                exc.missing_node_hash,
                self._starting_root_hash,
                exc.requested_key,
                self._address,
            ) from exc

    @property
    def has_changed_root(self) -> bool:
        return self._write_trie and self._write_trie.root_hash != self._starting_root_hash

    def get_changed_root(self) -> Hash32:
        if self._write_trie is not None:
            return self._write_trie.root_hash
        else:
            raise ValidationError("Asked for changed root when no writes have been made")

    def _clear_changed_root(self) -> None:
        self._write_trie = None
        self._trie_nodes_batch = None
        self._starting_root_hash = None

    def commit_to(self, db: BaseDB) -> None:
        """
        Trying to commit changes when nothing has been written will raise a
        ValidationError
        """
        self.logger.debug2('persist storage root to data store')
        if self._trie_nodes_batch is None:
            raise ValidationError(
                "It is invalid to commit an account's storage if it has no pending changes. "
                "Always check storage_lookup.has_changed_root before attempting to commit."
            )
        self._trie_nodes_batch.commit_to(db, apply_deletes=False)
        self._clear_changed_root()


class AccountStorageDB:
    """
    Storage cache and write batch for a single account. Changes are not
    merklized until :meth:`make_storage_root` is called.
    """
    logger = cast(ExtendedDebugLogger, logging.getLogger("eth.db.storage.AccountStorageDB"))

    def __init__(self, db: BaseAtomicDB, storage_root: Hash32, address: Address) -> None:
        """
        Database entries go through several pipes, like so...

        .. code::

            db -> _storage_lookup -> _storage_cache -> _journal_storage

        db is the raw database, we can assume it hits disk when written to.
        Keys are stored as node hashes and rlp-encoded node values.

        _storage_lookup is itself a pair of databases: (BatchDB -> HexaryTrie),
        writes to storage lookup *are* immeditaely applied to a trie, generating
        the appropriate trie nodes and and root hash (via the HexaryTrie). The
        writes are *not* persisted to db, until _storage_lookup is explicitly instructed to,
        via :meth:`StorageLookup.commit_to`

        _storage_cache is a cache tied to the state root of the trie. It
        is important that this cache is checked *after* looking for
        the key in _journal_storage, because the cache is only invalidated
        after a state root change. Otherwise, you will see data since the last
        storage root was calculated.

        Journaling batches writes at the _journal_storage layer, until persist is called.
        It manages all the checkpointing and rollbacks that happen during EVM execution.

        In both _storage_cache and _journal_storage, Keys are set/retrieved as the
        big_endian encoding of the slot integer, and the rlp-encoded value.
        """
        self._address = address
        self._storage_lookup = StorageLookup(db, storage_root, address)
        self._storage_cache = CacheDB(self._storage_lookup)
        self._journal_storage = JournalDB(self._storage_cache)

    def get(self, slot: int, from_journal: bool=True) -> int:
        key = int_to_big_endian(slot)
        lookup_db = self._journal_storage if from_journal else self._storage_cache
        try:
            encoded_value = lookup_db[key]
        except MissingStorageTrieNode:
            raise
        except KeyError:
            return 0

        if encoded_value == b'':
            return 0
        else:
            return rlp.decode(encoded_value, sedes=rlp.sedes.big_endian_int)

    def set(self, slot: int, value: int) -> None:
        key = int_to_big_endian(slot)
        if value:
            self._journal_storage[key] = rlp.encode(value)
        else:
            del self._journal_storage[key]

    def delete(self) -> None:
        self.logger.debug2(
            "Deleting all storage in account 0x%s, hashed 0x%s",
            self._address.hex(),
            keccak(self._address).hex(),
        )
        self._journal_storage.clear()
        self._storage_cache.reset_cache()

    def record(self, checkpoint: JournalDBCheckpoint) -> None:
        self._journal_storage.record(checkpoint)

    def discard(self, checkpoint: JournalDBCheckpoint) -> None:
        self.logger.debug2('discard checkpoint %r', checkpoint)
        if self._journal_storage.has_checkpoint(checkpoint):
            self._journal_storage.discard(checkpoint)
        else:
            # if the checkpoint comes before this account started tracking,
            #    then simply reset to the beginning
            self._journal_storage.reset()
        self._storage_cache.reset_cache()

    def commit(self, checkpoint: JournalDBCheckpoint) -> None:
        if self._journal_storage.has_checkpoint(checkpoint):
            self._journal_storage.commit(checkpoint)
        else:
            # if the checkpoint comes before this account started tracking,
            #    then flatten all changes, without persisting
            self._journal_storage.flatten()

    def make_storage_root(self) -> None:
        """
        Force calculation of the storage root for this account
        """
        self._journal_storage.persist()

    def _validate_flushed(self) -> None:
        """
        Will raise an exception if there are some changes made since the last persist.
        """
        journal_diff = self._journal_storage.diff()
        if len(journal_diff) > 0:
            raise ValidationError(
                "StorageDB had a dirty journal when it needed to be clean: %r" % journal_diff
            )

    @property
    def has_changed_root(self) -> bool:
        return self._storage_lookup.has_changed_root

    def get_changed_root(self) -> Hash32:
        return self._storage_lookup.get_changed_root()

    def persist(self, db: BaseDB) -> None:
        self._validate_flushed()
        if self._storage_lookup.has_changed_root:
            self._storage_lookup.commit_to(db)
