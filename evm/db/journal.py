import collections
from typing import Dict, Union  # noqa: F401
import uuid

from cytoolz import (
    first,
    merge,
    last,
)

from evm.db.backends.base import BaseDB
from evm.exceptions import ValidationError


class DeletedEntry:
    pass


DELETED_ENTRY = DeletedEntry()


class Journal(BaseDB):
    """
    A Journal is an ordered list of changesets.  A changeset is a dictionary
    of database keys and values.  The values are tracked changes that were
    written after the changeset was created

    Changesets are referenced by a random uuid4.
    """

    def __init__(self) -> None:
        # contains a mapping from all of the `uuid4` changeset_ids
        # to a dictionary of key:value pairs with the recorded changes
        # that belong to the changeset
        self.journal_data = collections.OrderedDict()  # type: collections.OrderedDict[uuid.UUID, Dict[bytes, Union[bytes, DeletedEntry]]]  # noqa E501

    @property
    def root_changeset_id(self) -> uuid.UUID:
        """
        Returns the id of the root changeset
        """
        return first(self.journal_data.keys())

    @property
    def latest_id(self) -> uuid.UUID:
        """
        Returns the id of the latest changeset
        """
        return last(self.journal_data.keys())

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

    def record_changeset(self) -> uuid.UUID:
        """
        Creates a new changeset. Changesets are referenced by a random uuid4
        to prevent collisions between multiple changesets.
        """
        changeset_id = uuid.uuid4()
        self.journal_data[changeset_id] = {}
        return changeset_id

    def pop_changeset(self, changeset_id: uuid.UUID) -> Dict[bytes, bytes]:
        """
        Returns all changes from the given changeset.  This includes all of
        the changes from any subsequent changeset, giving precidence to
        later changesets.
        """
        if changeset_id not in self.journal_data:
            raise KeyError("Unknown changeset: {0}".format(changeset_id))

        all_ids = tuple(self.journal_data.keys())
        changeset_idx = all_ids.index(changeset_id)
        changesets_to_pop = all_ids[changeset_idx:]

        # we pull all of the changesets *after* the changeset we are
        # reverting to and collapse them to a single set of keys (giving
        # precedence to later changesets)
        changeset_data = merge(*(
            self.journal_data.pop(c_id)
            for c_id
            in changesets_to_pop
        ))

        return changeset_data

    def commit_changeset(self, changeset_id: uuid.UUID) -> Dict[bytes, bytes]:
        """
        Collapses all changes for the given changeset into the previous
        changesets if it exists.
        """
        changeset_data = self.pop_changeset(changeset_id)
        if not self.is_empty():
            # we only have to merge the changes into the latest changeset if
            # there is one.
            self.latest = merge(
                self.latest,
                changeset_data,
            )
        return changeset_data

    #
    # Database API
    #
    def __getitem__(self, key: bytes) -> bytes:
        """
        For key lookups we need to iterate through the changesets in reverse
        order, returning from the first one in which the key is present.
        """
        # Ignored from mypy because of https://github.com/python/typeshed/issues/2078
        for changeset_data in reversed(self.journal_data.values()):  # type: ignore
            if key in changeset_data:
                return changeset_data[key]
            else:
                continue

        return None

    def __setitem__(self, key: bytes, value: bytes) -> None:
        self.latest[key] = value

    def _exists(self, key: bytes) -> bool:
        val = self.get(key)
        return val is not None and val is not DELETED_ENTRY

    def __delitem__(self, key: bytes) -> None:
        self.latest[key] = DELETED_ENTRY


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
            raise KeyError(key)
        elif val is None:
            return self.wrapped_db[key]
        else:
            return val

    def __setitem__(self, key: bytes, value: bytes) -> None:
        """
        - replacing an existing value
        - setting a value that does not exist
        """
        self.journal[key] = value

    def _exists(self, key: bytes) -> bool:
        return key in self.journal or key in self.wrapped_db

    def __delitem__(self, key: bytes) -> None:
        if key not in self.journal and key not in self.wrapped_db:
            raise KeyError(key)
        del self.journal[key]

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

    def record(self) -> uuid.UUID:
        """
        Starts a new recording and returns an id for the associated changeset
        """
        return self.journal.record_changeset()

    def discard(self, changeset_id: uuid.UUID) -> None:
        """
        Throws away all journaled data starting at the given changeset
        """
        self._validate_changeset(changeset_id)
        self.journal.pop_changeset(changeset_id)

    def commit(self, changeset_id: uuid.UUID) -> None:
        """
        Commits a given changeset. This merges the given changeset and all
        subsequent changesets into the previous changeset giving precidence
        to later changesets in case of any conflicting keys.

        If this is the base changeset then all changes will be written to
        the underlying database and the Journal starts a new recording.
        """
        self._validate_changeset(changeset_id)
        journal_data = self.journal.commit_changeset(changeset_id)

        if self.journal.is_empty():
            for key, value in journal_data.items():
                if value is not DELETED_ENTRY:
                    self.wrapped_db[key] = value
                else:
                    try:
                        del self.wrapped_db[key]
                    except KeyError:
                        pass

            # Ensure the journal automatically restarts recording after
            # it has been persisted to the underlying db
            self.reset()

    def persist(self) -> None:
        """
        Persist all changes in underlying db
        """
        self.commit(self.journal.root_changeset_id)

    def reset(self) -> None:
        """
        Reset the entire journal.
        """
        self.journal = Journal()
        self.record()
