from typing import Dict, List  # noqa: F401
import uuid

from cytoolz import (
    merge,
)

from evm.db.backends.base import BaseDB
from evm.exceptions import ValidationError


class Journal(object):
    """
    A Journal is an ordered list of checkpoints.  A checkpoint is a dictionary
    of database keys and values.  The values are the "original" value of that
    key at the time the checkpoint was created.

    Checkpoints are referenced by a random uuid4.
    """
    checkpoints = None  # type: List[uuid.UUID]

    def __init__(self):
        # contains an array of `uuid4` instances
        self.checkpoints = []
        # contains a mapping from all of the `uuid4` in the `checkpoints` array
        # to a dictionary of key:value pairs wher the `value` is the original
        # value for the given key at the moment this checkpoint was created.
        self.journal_data = {}  # type: Dict[uuid.UUID, Dict[bytes, bytes]]

        # TODO: Double check if this is the way to go. If I'm not mistaken, then
        # we have to start journaling (in order to cache!) from the very beginning
        # so creating a checkpoint on __init__ may be alright.
        self.create_checkpoint()

    @property
    def latest_id(self):
        """
        Returns the checkpoint_id of the latest checkpoint
        """
        return self.checkpoints[-1]

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

    def add(self, key, value):
        """
        Adds the given key and value to the latest checkpoint.
        """
        if not self.checkpoints:
            # If no checkpoints exist we don't need to track history.
            return

        self.latest[key] = value

    def get(self, key: bytes) -> bytes:
        """
        Returns the value for a given key from the journal by
        searching through the checkpoints in reverse order
        """
        for checkpoint in reversed(self.checkpoints):
            if key in self.journal_data[checkpoint]:
                return self.journal_data[checkpoint][key]

        return None

    def exists(self, key: bytes) -> bool:
        # TODO: Clarify
        # This is an inefficient lookup as we have to traverse all checkpoints
        # in order to figure out if a key exists in the journal at all.
        # We could keep track of keys in a set but the problem is that when
        # we pop or commit a checkpoint we can not simple remove a key from
        # the set because we do not know if it may still exist in a different
        # checkpoint. We could recompute all keys on every pop/commit though.
        return self.get(key) is not None

    def create_checkpoint(self):
        """
        Creates a new checkpoint.  Checkpoints are referenced by a random uuid4
        to prevent collisions between multiple checkpoints.
        """
        checkpoint_id = uuid.uuid4()
        self.checkpoints.append(checkpoint_id)
        self.journal_data[checkpoint_id] = {}
        return checkpoint_id

    def pop_checkpoint(self, checkpoint_id):
        """
        Returns all changes from the given checkpoint.  This includes all of
        the changes from any subsequent checkpoints, giving precidence to
        earlier checkpoints.
        """
        idx = self.checkpoints.index(checkpoint_id)

        # update the checkpoint list
        checkpoint_ids = self.checkpoints[idx:]
        self.checkpoints = self.checkpoints[:idx]

        # we pull all of the checkpoints *after* the checkpoint we are
        # reverting to and collapse them to a single set of keys that need to
        # be reverted (giving precidence to earlier checkpoints).
        revert_data = merge(*(
            self.journal_data.pop(c_id)
            for c_id
            in reversed(checkpoint_ids)
        ))

        return dict(revert_data.items())

    def commit_checkpoint(self, checkpoint_id):
        """
        Collapses all changes for the givent checkpoint into the previous
        checkpoint if it exists.
        """
        changes_to_merge = self.pop_checkpoint(checkpoint_id)
        if self.checkpoints:
            # we only have to merge the changes into the latest checkpoint if
            # there is one.
            self.latest = merge(
                changes_to_merge,
                self.latest,
            )

    def __contains__(self, value):
        return value in self.journal_data


class CachedJournalDB(BaseDB):
    """
    A wrapper around the basic DB objects that keeps a journal of all changes.
    Each time a snapshot is taken, the underlying journal creates a new
    checkpoint.  The journal then keeps track of the original value for any
    keys changed.  Reverting to a checkpoint involves merging the original key
    data from any subsequent checkpoints into the given checkpoint giving
    precidence earlier checkpoints.  Then the keys from this merged data set
    are reset to their original values.

    The added memory footprint for a JournalDB is one key/value stored per
    database key which is changed.  Subsequent changes to the same key within
    the same checkpoint will not increase the journal size since we only need
    to track the original value for any given key within any given checkpoint.
    """
    wrapped_db = None
    journal = None

    def __init__(self, wrapped_db):
        self.wrapped_db = wrapped_db
        self.journal = Journal()

    def get(self, key):
        val = self.journal.get(key)
        if val is not None:
            return val
        else:
            return self.wrapped_db.get(key)

    def set(self, key, value):
        self.journal.add(key, value)

    def exists(self, key):
        return self.journal.exists(key) or self.wrapped_db.exists(key)

    def delete(self, key):
        # TODO: If the journal is only supposed to work with bytes, using `None`
        # may be ok as a deletion marker. To make this more generic we should
        # probably use a dedicated type for that
        self.journal.add(key, None)

    #
    # Snapshot API
    #
    def _validate_checkpoint(self, checkpoint):
        """
        Checks to be sure the checkpoint is known by the journal
        """
        if checkpoint not in self.journal:
            raise ValidationError("Checkpoint not found in journal: {0}".format(
                str(checkpoint)
            ))

    def snapshot(self):
        """
        Takes a snapshot of the database by creating a checkpoint.
        """
        return self.journal.create_checkpoint()

    def revert(self, checkpoint):
        """
        Reverts the database back to the checkpoint.
        """
        self._validate_checkpoint(checkpoint)
        self.journal.pop_checkpoint(checkpoint)

    def commit(self, checkpoint):
        """
        Commits a given checkpoint.
        """
        self._validate_checkpoint(checkpoint)
        self.journal.commit_checkpoint(checkpoint)
        # TODO: write to underlying database

    def clear(self):
        """
        Cleare the entire journal.
        """
        self.journal = Journal()

    #
    # Dictionary API
    #
    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        return self.set(key, value)

    def __delitem__(self, key):
        return self.delete(key)

    def __contains__(self, key):
        return self.exists(key)
