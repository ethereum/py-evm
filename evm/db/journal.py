from evm.db.backends.base import BaseDB

from evm.validation import (
    validate_gte,
    validate_is_integer,
    validate_lte,
)


class JournalDB(BaseDB):
    """
    A wrapper around the basic DB objects that keeps a journal of all changes.
    Snapshots are simply indices into the list of journal entries.  Reversion
    involves replaying the journal entries in reverse until we reach the
    snapshot indices.

    This allows for linear runtime reversions to the state database.
    """
    wrapped_db = None
    journal = None

    def __init__(self, wrapped_db):
        self.wrapped_db = wrapped_db
        self.journal = []

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
            self.journal.append((key, current_value))

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
            self.journal.append((key, current_value))

        return self.wrapped_db.delete(key)

    #
    # Snapshot API
    #
    def _validate_journal_index(self, journal_index):
        validate_is_integer(journal_index, title="Journal index")
        validate_gte(journal_index, 0, title="Journal index")
        validate_lte(journal_index, len(self.journal), title="Journal index")

    def snapshot(self):
        return len(self.journal)

    def revert(self, journal_index):
        self._validate_journal_index(journal_index)

        while len(self.journal) > journal_index:
            key, previous_value = self.journal.pop()
            if previous_value is None:
                self.wrapped_db.delete(key)
            else:
                self.wrapped_db.set(key, previous_value)

    def clear_journal(self, journal_index):
        self._validate_journal_index(journal_index)
        self.journal = self.journal[journal_index:]

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
