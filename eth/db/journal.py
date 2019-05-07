import collections
from itertools import (
    count,
)
from typing import cast, Dict, Set, Union  # noqa: F401
import uuid

from eth_utils.toolz import (
    first,
    merge,
    nth,
)
from eth_utils import (
    to_tuple,
    ValidationError,
)

from eth.db.backends.base import BaseDB
from eth.db.diff import DBDiff, DBDiffTracker


class DeletedEntry:
    pass


# Track two different kinds of deletion:

# 1. key in wrapped
# 2. key modified in journal
# 3. key deleted
DELETED_ENTRY = DeletedEntry()

# 1. key not in wrapped
# 2. key created in journal
# 3. key deleted
ERASE_CREATED_ENTRY = DeletedEntry()


class ValueDelta:
    pass


REVERT_TO_ORIGINAL = ValueDelta()


id_generator = count()


class Journal(BaseDB):
    """
    A Journal is an ordered list of changesets.  A changeset is a dictionary
    of database keys and values.  The values are tracked changes which give
    the information needed to revert a changeset to an old checkpoint.

    Changesets are referenced by an internally-generated integer.
    """

    def __init__(self) -> None:
        # contains a mapping from all of the `uuid4` changeset_ids
        # to a dictionary of key:value pairs that describe how to rewind from the current values
        # to the given checkpoint
        self.journal_data = collections.OrderedDict()  # type: collections.OrderedDict[uuid.UUID, Dict[bytes, Union[bytes, DeletedEntry]]]  # noqa E501
        self._clears_at = set()  # type: Set[uuid.UUID]
        self._current_values = {}  # Dict[bytes, Union[bytes, DeletedEntry]]
        self._is_cleared = False

    @property
    def root_changeset_id(self) -> uuid.UUID:
        """
        Returns the id of the root changeset
        """
        return first(self.journal_data.keys())

    @property
    def is_flattened(self) -> bool:
        """
        :return: whether there are any explicitly committed checkpoints
        """
        return len(self.journal_data) < 2

    @property
    def latest_id(self) -> uuid.UUID:
        """
        Returns the id of the latest changeset
        """
        # last() was iterating through all values, so first(reversed()) gives a 12.5x speedup
        # Interestingly, an attempt to cache this value caused a slowdown.
        return first(reversed(self.journal_data.keys()))

    @property
    def latest(self) -> Dict[bytes, Union[bytes, DeletedEntry]]:
        """
        Returns the dictionary of db keys and values for the latest changeset.
        """
        return self.journal_data[self.latest_id]

    @latest.setter
    def latest(self, value: Dict[bytes, Union[bytes, DeletedEntry]]) -> None:
        """
        Setter for updating the *latest* changeset.
        """
        self.journal_data[self.latest_id] = value

    def is_empty(self) -> bool:
        return len(self.journal_data) == 0

    def has_changeset(self, changeset_id: uuid.UUID) -> bool:
        return changeset_id in self.journal_data

    def record_changeset(self, custom_changeset_id: uuid.UUID = None) -> uuid.UUID:
        """
        Creates a new changeset. Changesets are referenced by a random uuid4
        to prevent collisions between multiple changesets.
        """
        if custom_changeset_id is not None:
            if custom_changeset_id in self.journal_data:
                raise ValidationError(
                    "Tried to record with an existing changeset id: %r" % custom_changeset_id
                )
            else:
                changeset_id = custom_changeset_id
        else:
            changeset_id = next(id_generator)

        self.journal_data[changeset_id] = {}
        return changeset_id

    def discard(self, discard_through_checkpoint_id):
        for checkpoint_id, rollback_data in self._rollbacks_through(discard_through_checkpoint_id):
            for old_key, old_value in rollback_data.items():
                if old_value is REVERT_TO_ORIGINAL:
                    del self._current_values[old_key]
                else:
                    self._current_values[old_key] = old_value

            del self.journal_data[checkpoint_id]

            if checkpoint_id in self._clears_at:
                self._clears_at.remove(checkpoint_id)
                self._is_cleared = False

        if self._clears_at:
            # if there is still a clear in older locations, then reinitiate the clear flag
            self._is_cleared = True

    @to_tuple
    def _rollbacks_through(self, through_checkpoint_id):
        for checkpoint_id, rollback_data in reversed(self.journal_data.items()):
            yield checkpoint_id, rollback_data
            if checkpoint_id == through_checkpoint_id:
                break
        else:
            # checkpoint not found!
            raise ValidationError("No checkpoint %s was found" % through_checkpoint_id)

    def _drop_rollbacks(self, drop_through_checkpoint_id: uuid.UUID) -> Dict[bytes, Union[bytes, DeletedEntry]]:
        had_clear = False
        for checkpoint_id, _ in self._rollbacks_through(drop_through_checkpoint_id):
            del self.journal_data[checkpoint_id]

            if checkpoint_id in self._clears_at:
                self._clears_at.remove(checkpoint_id)
                had_clear = True

        return had_clear

    def clear(self) -> None:
        """
        Treat as if the *underlying* database will also be cleared by some other mechanism.
        We build a special empty changeset just for marking that all previous data should
        be ignored.
        """
        changeset_id = next(id_generator)
        self.journal_data[changeset_id] = self._current_values
        self._current_values = {}
        self._is_cleared = True
        self._clears_at.add(changeset_id)

    def has_clear(self, check_changeset_id: uuid.UUID) -> bool:
        for changeset_id in reversed(self.journal_data.keys()):
            if changeset_id in self._clears_at:
                return True
            elif check_changeset_id == changeset_id:
                return False
        raise ValidationError("Changeset ID %s is not in the journal" % check_changeset_id)

    def commit_changeset(self, changeset_id: uuid.UUID) -> Dict[bytes, Union[bytes, DeletedEntry]]:
        """
        Collapses all changes for the given changeset into the previous
        changesets if it exists.
        """
        does_clear = self._drop_rollbacks(changeset_id)
        if not self.is_empty():
            # we only have to assign changeset data into the latest changeset if
            # there is one.
            if does_clear:
                # if there was a clear and more changesets underneath then clear the latest
                # changeset, and replace with a new clear changeset
                self.latest = {}
                self._clears_at.add(self.latest_id)
                self.record_changeset()
        return self._current_values

    def flatten(self) -> None:
        if self.is_flattened:
            return

        changeset_id_after_root = nth(1, self.journal_data.keys())
        self.commit_changeset(changeset_id_after_root)

    #
    # Database API
    #
    def __getitem__(self, key: bytes) -> Union[bytes, DeletedEntry]:    # type: ignore # Breaks LSP
        """
        For key lookups we need to iterate through the changesets in reverse
        order, returning from the first one in which the key is present.
        """
        # the default result (the value if not in the local values) depends on whether there
        # was a clear
        if self._is_cleared:
            default_result = ERASE_CREATED_ENTRY
        else:
            default_result = None  # indicate that caller should check wrapped database
        return self._current_values.get(key, default_result)

        '''
        for changeset_id, changeset_data in reversed(self.journal_data.items()):
            if changeset_id in self._clears_at:
                return ERASE_CREATED_ENTRY
            elif key in changeset_data:
                return changeset_data[key]
            else:
                continue

        return None
    '''

    def __setitem__(self, key: bytes, value: bytes) -> None:
        # if the value has not been changed since wrapping, then simply revert to original value
        revert_changeset = self.latest
        if key not in revert_changeset:
            revert_changeset[key] = self._current_values.get(key, REVERT_TO_ORIGINAL)
        self._current_values[key] = value

    def _exists(self, key: bytes) -> bool:
        val = self.get(key)
        return val is not None and val not in (ERASE_CREATED_ENTRY, DELETED_ENTRY)

    def __delitem__(self, key: bytes) -> None:
        raise NotImplementedError("You must delete with one of delete_local or delete_wrapped")

    def delete_wrapped(self, key: bytes) -> None:
        revert_changeset = self.latest
        if key not in revert_changeset:
            revert_changeset[key] = self._current_values.get(key, REVERT_TO_ORIGINAL)
        self._current_values[key] = DELETED_ENTRY

    def delete_local(self, key: bytes) -> None:
        revert_changeset = self.latest
        if key not in revert_changeset:
            revert_changeset[key] = self._current_values.get(key, REVERT_TO_ORIGINAL)
        self._current_values[key] = ERASE_CREATED_ENTRY

    def diff(self) -> DBDiff:
        tracker = DBDiffTracker()

        for key, value in self._current_values.items():
            if value is DELETED_ENTRY:
                del tracker[key]
            elif value is ERASE_CREATED_ENTRY:
                pass
            else:
                tracker[key] = value  # type: ignore  # cast(bytes, value)

        return tracker.diff()


class JournalDB(BaseDB):
    """
    A wrapper around the basic DB objects that keeps a journal of all changes.
    Each time a recording is started, the underlying journal creates a new
    changeset and assigns an id to it. The journal then keeps track of all changes
    that go into this changeset.

    Discarding a changeset simply throws it away inculding all subsequent changesets
    that may have followed. Commiting a changeset merges the given changeset and all
    subsequent changesets into the previous changeset giving precidence to later
    changesets in case of conflicting keys.

    Nothing is written to the underlying db until `persist()` is called.

    The added memory footprint for a JournalDB is one key/value stored per
    database key which is changed.  Subsequent changes to the same key within
    the same changeset will not increase the journal size since we only need
    to track latest value for any given key within any given changeset.
    """
    wrapped_db = None
    journal = None  # type: Journal

    def __init__(self, wrapped_db: BaseDB) -> None:
        self.wrapped_db = wrapped_db
        self.reset()

    def __getitem__(self, key: bytes) -> bytes:

        val = self.journal[key]
        if val is DELETED_ENTRY:
            raise KeyError(
                key,
                "item is deleted in JournalDB, and will be deleted from the wrapped DB",
            )
        elif val is ERASE_CREATED_ENTRY:
            raise KeyError(
                key,
                "item is deleted in JournalDB, and is presumed gone from the wrapped DB",
            )
        elif val is None:
            return self.wrapped_db[key]
        else:
            # mypy doesn't allow custom type guards yet so we need to cast here
            # even though we know it can only be `bytes` at this point.
            return cast(bytes, val)

    def __setitem__(self, key: bytes, value: bytes) -> None:
        """
        - replacing an existing value
        - setting a value that does not exist
        """
        self.journal[key] = value

    def _exists(self, key: bytes) -> bool:
        val = self.journal[key]
        if val in (ERASE_CREATED_ENTRY, DELETED_ENTRY):
            return False
        elif val is None:
            return key in self.wrapped_db
        else:
            return True

    def clear(self) -> None:
        """
        Remove all keys. Immediately after a clear, *all* getitem requests will return a KeyError.
        That includes the changes pending persist and any data in the underlying database.

        (This action is journaled, like all other actions)

        clear will *not* persist the emptying of all keys in the underlying DB.
        It only prevents any updates (or deletes!) before it from being persisted.

        Any caller that wants to use clear must also make sure that the underlying database
        reflects their desired end state (maybe emptied, maybe not).
        """
        self.journal.clear()

    def has_clear(self) -> bool:
        return self.journal.has_clear(self.journal.root_changeset_id)

    def __delitem__(self, key: bytes) -> None:
        if key in self.wrapped_db:
            self.journal.delete_wrapped(key)
        else:
            if key in self.journal:
                self.journal.delete_local(key)
            else:
                raise KeyError(key, "key could not be deleted in JournalDB, because it was missing")

    #
    # Snapshot API
    #
    def _validate_changeset(self, changeset_id: uuid.UUID) -> None:
        """
        Checks to be sure the changeset is known by the journal
        """
        if not self.journal.has_changeset(changeset_id):
            raise ValidationError("Changeset not found in journal: {0}".format(
                str(changeset_id)
            ))

    def has_changeset(self, changeset_id: uuid.UUID) -> bool:
        return self.journal.has_changeset(changeset_id)

    def record(self, custom_changeset_id: uuid.UUID = None) -> uuid.UUID:
        """
        Starts a new recording and returns an id for the associated changeset
        """
        return self.journal.record_changeset(custom_changeset_id)

    def discard(self, changeset_id: uuid.UUID) -> None:
        """
        Throws away all journaled data starting at the given changeset
        """
        self._validate_changeset(changeset_id)
        self.journal.discard(changeset_id)

    def commit(self, changeset_id: uuid.UUID) -> None:
        """
        Commits a given changeset. This merges the given changeset and all
        subsequent changesets into the previous changeset giving precidence
        to later changesets in case of any conflicting keys.
        """
        self._validate_changeset(changeset_id)
        if changeset_id == self.journal.root_changeset_id:
            raise ValidationError(
                "Tried to commit the root changeset. Callers should not keep references "
                "to the root changeset. Maybe you meant to use persist()?"
            )
        self.journal.commit_changeset(changeset_id)

    def _reapply_changeset_to_journal(
            self,
            changeset_id: uuid.UUID,
            journal_data: Dict[bytes, Union[bytes, DeletedEntry]]) -> None:
        self.record(changeset_id)
        for key, value in journal_data.items():
            if value is DELETED_ENTRY:
                self.journal.delete_wrapped(key)
            elif value is ERASE_CREATED_ENTRY:
                self.journal.delete_local(key)
            else:
                self.journal[key] = cast(bytes, value)

    def persist(self) -> None:
        """
        Persist all changes in underlying db. After all changes have been written the
        JournalDB starts a new recording.
        """
        root_changeset = self.journal.root_changeset_id
        journal_data = self.journal.commit_changeset(root_changeset)

        # Ensure the journal automatically restarts recording after
        # it has been persisted to the underlying db
        self.reset()

        for key, value in journal_data.items():
            try:
                if value is DELETED_ENTRY:
                    del self.wrapped_db[key]
                elif value is ERASE_CREATED_ENTRY:
                    pass
                else:
                    self.wrapped_db[key] = cast(bytes, value)
            except Exception:
                self._reapply_changeset_to_journal(root_changeset, journal_data)
                raise

    def flatten(self) -> None:
        """
        Commit everything possible without persisting
        """
        self.journal.flatten()

    def reset(self) -> None:
        """
        Reset the entire journal.
        """
        self.journal = Journal()
        self.record()

    def diff(self) -> DBDiff:
        """
        Generate a DBDiff of all pending changes.
        These are the changes that would occur if :meth:`persist()` were called.
        """
        return self.journal.diff()
