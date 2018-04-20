import collections
from typing import Dict  # noqa: F401
import uuid

from cytoolz import (
    first,
    merge,
    last,
)

from evm.db.backends.base import BaseDB
from evm.exceptions import ValidationError


class Journal(BaseDB):
    """
    A Journal is an ordered list of checkpoints.  A checkpoint is a dictionary
    of database keys and values.  The values are the "original" value of that
    key at the time the checkpoint was created.

    Checkpoints are referenced by a random uuid4.
    """

    def __init__(self):
        # contains a mapping from all of the `uuid4` in the `checkpoints` array
        # to a dictionary of key:value pairs wher the `value` is the original
        # value for the given key at the moment this checkpoint was created.
        self.journal_data = collections.OrderedDict()  # type: collections.OrderedDict[uuid.UUID, Dict[bytes, bytes]]  # noqa E501

    @property
    def root_checkpoint_id(self):
        """
        Returns the checkpoint_id of the latest checkpoint
        """
        return first(self.journal_data.keys())

    @property
    def latest_id(self):
        """
        Returns the checkpoint_id of the latest checkpoint
        """
        return last(self.journal_data.keys())

    @property
    def latest(self):
        """
        Returns the dictionary of db keys and values for the latest checkpoint.
        """
        return self.journal_data[self.latest_id]

    @latest.setter
    def latest(self, value):
        """
        Setter for updating the *latest* checkpoint.
        """
        self.journal_data[self.latest_id] = value

    def is_empty(self):
        return len(self.journal_data) == 0

    def has_checkpoint(self, checkpoint_id):
        return checkpoint_id in self.journal_data

    def create_checkpoint(self):
        """
        Creates a new checkpoint. Checkpoints are referenced by a random uuid4
        to prevent collisions between multiple checkpoints.
        """
        checkpoint_id = uuid.uuid4()
        self.journal_data[checkpoint_id] = {}
        return checkpoint_id

    def pop_checkpoint(self, checkpoint_id):
        """
        Returns all changes from the given checkpoint.  This includes all of
        the changes from any subsequent checkpoints, giving precidence to
        later checkpoints.
        """
        if checkpoint_id not in self.journal_data:
            raise KeyError("Unknown checkpoint: {0}".format(checkpoint_id))

        all_ids = tuple(self.journal_data.keys())
        checkpoint_idx = all_ids.index(checkpoint_id)
        checkpoints_to_pop = all_ids[checkpoint_idx:]

        # we pull all of the checkpoints *after* the checkpoint we are
        # reverting to and collapse them to a single set of keys (giving
        # precedence to later checkpoints)
        checkpoint_data = merge(*(
            self.journal_data.pop(c_id)
            for c_id
            in checkpoints_to_pop
        ))

        return checkpoint_data

    def commit_checkpoint(self, checkpoint_id):
        """
        Collapses all changes for the given checkpoint into the previous
        checkpoint if it exists.
        """
        checkpoint_data = self.pop_checkpoint(checkpoint_id)
        if not self.is_empty():
            # we only have to merge the changes into the latest checkpoint if
            # there is one.
            self.latest = merge(
                self.latest,
                checkpoint_data,
            )
        return checkpoint_data

    #
    # Database API
    #
    def get(self, key):
        """
        For key lookups we need to iterate through the checkpoints in reverse
        order, returning from the first one in which the key is present.
        """
        for checkpoint_data in reversed(self.journal_data.values()):
            try:
                value = checkpoint_data[key]
            except KeyError:
                continue
            else:
                if value is None:
                    raise KeyError(key)
                else:
                    return value
        else:
            raise KeyError(key)

    def set(self, key, value):
        self.latest[key] = value

    def exists(self, key):
        for checkpoint_data in reversed(self.journal_data.values()):
            try:
                value = checkpoint_data[key]
            except KeyError:
                continue
            else:
                if value is None:
                    return False
                else:
                    return True
        else:
            return False

    def delete(self, key):
        self.latest[key] = None


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
    to track latest value for any given key within any given checkpoint.
    """
    wrapped_db = None
    journal = None  # type: Journal

    def __init__(self, wrapped_db: BaseDB) -> None:
        self.wrapped_db = wrapped_db
        self.clear()

    # TODO: Measure perf impact of exception ping pong
    def get(self, key: bytes) -> bytes:
        try:
            return self.journal[key]
        except KeyError:
            return self.wrapped_db[key]

    def set(self, key: bytes, value: bytes) -> None:
        """
        - replacing an existing value
        - setting a value that does not exist
        """
        self.journal[key] = value

    def exists(self, key):
        return key in self.journal or key in self.wrapped_db

    def delete(self, key):
        if key not in self.journal and key not in self.wrapped_db:
            raise KeyError(key)
        del self.journal[key]

    #
    # Snapshot API
    #
    def _validate_checkpoint(self, checkpoint):
        """
        Checks to be sure the checkpoint is known by the journal
        """
        if not self.journal.has_checkpoint(checkpoint):
            raise ValidationError("Checkpoint not found in journal: {0}".format(
                str(checkpoint)
            ))

    def record(self):
        """
        Starts a new recording and returns an id for the associated changeset
        """
        return self.journal.create_checkpoint()

    def discard(self, changeset):
        """
        Throws away all journaled data starting at the given changeset
        """
        self._validate_checkpoint(changeset)
        self.journal.pop_checkpoint(changeset)

    def commit(self, checkpoint):
        """
        Commits a given checkpoint. This involves committing the journal up to
        the given checkpoint which returns all of the journal changes.  *if*
        this is the base checkpoint then all journal data should be committed
        to the underlying database.
        """
        self._validate_checkpoint(checkpoint)
        journal_data = self.journal.commit_checkpoint(checkpoint)

        if self.journal.is_empty():
            for key, value in journal_data.items():
                if value is not None:
                    self.wrapped_db[key] = value
                else:
                    try:
                        del self.wrapped_db[key]
                    except KeyError:
                        pass

            # ensure new root checkpoint
            self.journal.create_checkpoint()

    def persist(self):
        """
        Persist all changes in underlying db
        """
        self.commit(self.journal.root_checkpoint_id)

    # TODO: rename to reset
    def clear(self):
        """
        Cleare the entire journal.
        """
        self.journal = Journal()
        self.record()

    # temporary aliases to assist refactoring
    def snapshot(self):
        return self.record()

    def revert(self, changeset):
        return self.discard(changeset)
