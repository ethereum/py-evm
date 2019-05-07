import collections
from itertools import (
    count,
)
from typing import Callable, cast, Dict, List, Set, Union  # noqa: F401

from eth_utils.toolz import (
    first,
    nth,
)
from eth_utils import (
    ValidationError,
)

from .backends.base import BaseDB
from .diff import DBDiff, DBDiffTracker
from .typing import JournalDBCheckpoint


class DeletedEntry:
    pass


# Track two different kinds of deletion:

# 1. key in wrapped
# 2. key modified in journal
# 3. key deleted
DELETE_WRAPPED = DeletedEntry()

# 1. key not in wrapped
# 2. key created in journal
# 3. key deleted
REVERT_TO_WRAPPED = DeletedEntry()

ChangesetValue = Union[bytes, DeletedEntry]
ChangesetDict = Dict[bytes, ChangesetValue]

get_next_checkpoint_id = cast(Callable[[], JournalDBCheckpoint], count().__next__)


class Journal(BaseDB):
    """
    A Journal is an ordered list of changesets.  A changeset is a dictionary
    of database keys and values.  The values are tracked changes which give
    the information needed to revert a changeset to an old checkpoint.

    Changesets are referenced by an internally-generated integer. This is *not* threadsafe.
    """
    __slots__ = [
        '_journal_data',
        '_clears_at',
        '_current_values',
        '_ignore_wrapped_db',
        '_checkpoint_stack',
    ]

    #
    # This is a high-use class, where we sometimes prefere optimization over readability.
    # It's most important to optimize for record, commit, and persist, which ard the most commonly
    # used methods.
    #

    def __init__(self) -> None:
        # contains a mapping from all of the int changeset_ids
        # to a dictionary of key:value pairs that describe how to rewind from the current values
        # to the given checkpoint
        self._journal_data = collections.OrderedDict()  # type: collections.OrderedDict[JournalDBCheckpoint, ChangesetDict]  # noqa E501
        self._clears_at = set()  # type: Set[JournalDBCheckpoint]

        # If the journal was persisted right now, these would be the current changes to push:
        self._current_values = {}  # type: ChangesetDict

        # If a clear was called, then any missing keys should be treated as missing
        self._ignore_wrapped_db = False

        # To speed up commits, we leave in old recorded checkpoints on commit and keep a separate
        # list of active checkpoints.
        self._checkpoint_stack = []  # type: List[JournalDBCheckpoint]

    @property
    def root_changeset_id(self) -> JournalDBCheckpoint:
        """
        Returns the id of the root changeset
        """
        return first(self._journal_data.keys())

    @property
    def is_flattened(self) -> bool:
        """
        :return: whether there are any explicitly committed checkpoints
        """
        return len(self._checkpoint_stack) < 2

    @property
    def last_changeset_index(self) -> JournalDBCheckpoint:
        """
        Returns the id of the latest changeset
        """
        # last() was iterating through all values, so first(reversed()) gives a 12.5x speedup
        # Interestingly, an attempt to cache this value caused a slowdown.
        return first(reversed(self._journal_data.keys()))

    def has_changeset(self, changeset_id: JournalDBCheckpoint) -> bool:
        # another option would be to enforce monotonically-increasing changeset ids, so we can do:
        # checkpoint_idx = bisect_left(self._checkpoint_stack, changeset_id)
        # (then validate against length and value at index)
        return changeset_id in self._checkpoint_stack

    def record_changeset(
            self,
            custom_changeset_id: JournalDBCheckpoint = None) -> JournalDBCheckpoint:
        """
        Creates a new changeset. Changesets are referenced by a random int
        to prevent collisions between multiple changesets.
        """
        if custom_changeset_id is not None:
            if custom_changeset_id in self._journal_data:
                raise ValidationError(
                    "Tried to record with an existing changeset id: %r" % custom_changeset_id
                )
            else:
                changeset_id = custom_changeset_id
        else:
            changeset_id = get_next_checkpoint_id()

        self._journal_data[changeset_id] = {}
        self._checkpoint_stack.append(changeset_id)
        return changeset_id

    def discard(self, through_checkpoint_id: JournalDBCheckpoint) -> None:
        while self._checkpoint_stack:
            checkpoint_id = self._checkpoint_stack.pop()
            if checkpoint_id == through_checkpoint_id:
                break
        else:
            # checkpoint not found!
            raise ValidationError("No checkpoint %s was found" % through_checkpoint_id)

        # This might be optimized further by iterating the other direction and
        # ignoring any follow-up rollbacks on the same variable.
        for _ in range(len(self._journal_data)):
            checkpoint_id, rollback_data = self._journal_data.popitem()

            for old_key, old_value in rollback_data.items():
                if old_value is REVERT_TO_WRAPPED:
                    # The current value may not exist, if it was a delete followed by a clear,
                    # so pop it off, or ignore if it is already missing
                    self._current_values.pop(old_key, None)
                elif old_value is DELETE_WRAPPED:
                    self._current_values[old_key] = old_value
                elif type(old_value) is bytes:
                    self._current_values[old_key] = old_value
                else:
                    raise ValidationError("Unexpected value, must be bytes: %r" % old_value)

            if checkpoint_id in self._clears_at:
                self._clears_at.remove(checkpoint_id)
                self._ignore_wrapped_db = False

            if checkpoint_id == through_checkpoint_id:
                break

        if self._clears_at:
            # if there is still a clear in older locations, then reinitiate the clear flag
            self._ignore_wrapped_db = True

    def clear(self) -> None:
        """
        Treat as if the *underlying* database will also be cleared by some other mechanism.
        We build a special empty changeset just for marking that all previous data should
        be ignored.
        """
        changeset_id = get_next_checkpoint_id()
        self._journal_data[changeset_id] = self._current_values
        self._current_values = {}
        self._ignore_wrapped_db = True
        self._clears_at.add(changeset_id)

    def has_clear(self, check_changeset_id: JournalDBCheckpoint) -> bool:
        for changeset_id in reversed(self._journal_data.keys()):
            if changeset_id in self._clears_at:
                return True
            elif check_changeset_id == changeset_id:
                return False
        raise ValidationError("Changeset ID %s is not in the journal" % check_changeset_id)

    def commit_changeset(self, commit_id: JournalDBCheckpoint) -> ChangesetDict:
        """
        Collapses all changes for the given changeset into the previous
        changesets if it exists.
        """
        # Another option would be to enforce monotonically-increasing changeset ids, so we can do:
        # checkpoint_idx = bisect_left(self._checkpoint_stack, commit_id)
        # (then validate against length and value at index)
        for positions_before_last, checkpoint in enumerate(reversed(self._checkpoint_stack)):
            if checkpoint == commit_id:
                checkpoint_idx = -1 - positions_before_last
                break
        else:
            raise ValidationError("No checkpoint %s was found" % commit_id)

        if checkpoint_idx == -1 * len(self._checkpoint_stack):
            raise ValidationError(
                "Should not commit root changeset with commit_changeset, use pop_all() instead"
            )

        # delete committed checkpoints from the stack (but keep rollbacks for future discards)
        del self._checkpoint_stack[checkpoint_idx:]

        return self._current_values

    def pop_all(self) -> ChangesetDict:
        final_changes = self._current_values
        self._journal_data.clear()
        self._clears_at.clear()
        self._current_values = {}
        self._checkpoint_stack.clear()
        self.record_changeset()
        return final_changes

    def flatten(self) -> None:
        if self.is_flattened:
            return

        changeset_id_after_root = nth(1, self._checkpoint_stack)
        self.commit_changeset(changeset_id_after_root)

    #
    # Database API
    #
    def __getitem__(self, key: bytes) -> ChangesetValue:    # type: ignore # Breaks LSP
        """
        For key lookups we need to iterate through the changesets in reverse
        order, returning from the first one in which the key is present.
        """
        # the default result (the value if not in the local values) depends on whether there
        # was a clear
        if self._ignore_wrapped_db:
            default_result = REVERT_TO_WRAPPED
        else:
            default_result = None  # indicate that caller should check wrapped database
        return self._current_values.get(key, default_result)

    def __setitem__(self, key: bytes, value: bytes) -> None:
        # if the value has not been changed since wrapping, then simply revert to original value
        revert_changeset = self._journal_data[self.last_changeset_index]
        if key not in revert_changeset:
            revert_changeset[key] = self._current_values.get(key, REVERT_TO_WRAPPED)
        self._current_values[key] = value

    def _exists(self, key: bytes) -> bool:
        val = self.get(key)
        return val is not None and val not in (REVERT_TO_WRAPPED, DELETE_WRAPPED)

    def __delitem__(self, key: bytes) -> None:
        raise NotImplementedError("You must delete with one of delete_local or delete_wrapped")

    def delete_wrapped(self, key: bytes) -> None:
        revert_changeset = self._journal_data[self.last_changeset_index]
        if key not in revert_changeset:
            revert_changeset[key] = self._current_values.get(key, REVERT_TO_WRAPPED)
        self._current_values[key] = DELETE_WRAPPED

    def delete_local(self, key: bytes) -> None:
        revert_changeset = self._journal_data[self.last_changeset_index]
        if key not in revert_changeset:
            revert_changeset[key] = self._current_values.get(key, REVERT_TO_WRAPPED)
        self._current_values[key] = REVERT_TO_WRAPPED

    def diff(self) -> DBDiff:
        tracker = DBDiffTracker()

        for key, value in self._current_values.items():
            if value is DELETE_WRAPPED:
                del tracker[key]
            elif value is REVERT_TO_WRAPPED:
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
    __slots__ = ['_wrapped_db', '_journal', 'record', 'commit']

    def __init__(self, wrapped_db: BaseDB) -> None:
        self._wrapped_db = wrapped_db
        self._journal = Journal()
        self.record = self._journal.record_changeset
        self.commit = self._journal.commit_changeset
        self.reset()

    def __getitem__(self, key: bytes) -> bytes:

        val = self._journal[key]
        if val is DELETE_WRAPPED:
            raise KeyError(
                key,
                "item is deleted in JournalDB, and will be deleted from the wrapped DB",
            )
        elif val is REVERT_TO_WRAPPED:
            raise KeyError(
                key,
                "item is deleted in JournalDB, and is presumed gone from the wrapped DB",
            )
        elif val is None:
            return self._wrapped_db[key]
        else:
            # mypy doesn't allow custom type guards yet so we need to cast here
            # even though we know it can only be `bytes` at this point.
            return cast(bytes, val)

    def __setitem__(self, key: bytes, value: bytes) -> None:
        """
        - replacing an existing value
        - setting a value that does not exist
        """
        self._journal[key] = value

    def _exists(self, key: bytes) -> bool:
        val = self._journal[key]
        if val in (REVERT_TO_WRAPPED, DELETE_WRAPPED):
            return False
        elif val is None:
            return key in self._wrapped_db
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
        self._journal.clear()

    def has_clear(self) -> bool:
        return self._journal.has_clear(self._journal.root_changeset_id)

    def __delitem__(self, key: bytes) -> None:
        if key in self._wrapped_db:
            self._journal.delete_wrapped(key)
        else:
            if key in self._journal:
                self._journal.delete_local(key)
            else:
                raise KeyError(key, "key could not be deleted in JournalDB, because it was missing")

    #
    # Snapshot API
    #
    def has_changeset(self, changeset_id: JournalDBCheckpoint) -> bool:
        return self._journal.has_changeset(changeset_id)

    def discard(self, changeset_id: JournalDBCheckpoint) -> None:
        """
        Throws away all journaled data starting at the given changeset
        """
        self._journal.discard(changeset_id)

    def _reapply_changeset_to_journal(
            self,
            journal_data: ChangesetDict) -> None:
        for key, value in journal_data.items():
            if value is DELETE_WRAPPED:
                self._journal.delete_wrapped(key)
            elif value is REVERT_TO_WRAPPED:
                self._journal.delete_local(key)
            else:
                self._journal[key] = cast(bytes, value)

    def persist(self) -> None:
        """
        Persist all changes in underlying db. After all changes have been written the
        JournalDB starts a new recording.
        """
        journal_data = self._journal.pop_all()

        for key, value in journal_data.items():
            try:
                if value is DELETE_WRAPPED:
                    del self._wrapped_db[key]
                elif value is REVERT_TO_WRAPPED:
                    pass
                else:
                    self._wrapped_db[key] = cast(bytes, value)
            except Exception:
                self._reapply_changeset_to_journal(journal_data)
                raise

    def flatten(self) -> None:
        """
        Commit everything possible without persisting
        """
        self._journal.flatten()

    def reset(self) -> None:
        """
        Reset the entire journal.
        """
        self._journal.pop_all()

    def diff(self) -> DBDiff:
        """
        Generate a DBDiff of all pending changes.
        These are the changes that would occur if :meth:`persist()` were called.
        """
        return self._journal.diff()
