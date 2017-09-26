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
    checkpoints = None

    def __init__(self):
        # contains an array of `uuid4` instances
        self.checkpoints = []
        # contains a mapping from all of the `uuid4` in the `checkpoints` array
        # to a dictionary of key:value pairs wher the `value` is the original
        # value for the given key at the moment this checkpoint was created.
        self.journal_data = {}

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
        elif key in self.latest:
            # If the key is already in the latest checkpoint we should not
            # overwrite it.
            return
        self.latest[key] = value

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


class JournalDB(BaseDB):
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
        return self.wrapped_db.get(key)

    def set(self, key, value):
        """
        - replacing an existing value
        - setting a value that does not exist
        """
        try:
            current_value = self.wrapped_db.get(key)
        except KeyError:
            current_value = None

        if current_value != value:
            # only journal `set` operations that change the value.
            self.journal.add(key, current_value)

        return self.wrapped_db.set(key, value)

    def exists(self, key):
        return self.wrapped_db.exists(key)

    def delete(self, key):
        try:
            current_value = self.wrapped_db.get(key)
        except KeyError:
            # no state change so skip journaling
            pass
        else:
            self.journal.add(key, current_value)

        return self.wrapped_db.delete(key)

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

        for key, value in self.journal.pop_checkpoint(checkpoint).items():
            if value is None:
                self.wrapped_db.delete(key)
            else:
                self.wrapped_db.set(key, value)

    def commit(self, checkpoint):
        """
        Commits a given checkpoint.
        """
        self._validate_checkpoint(checkpoint)
        self.journal.commit_checkpoint(checkpoint)

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
