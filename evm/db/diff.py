from collections.abc import (
    Mapping,
    MutableMapping,
)
from typing import (  # noqa: F401
    Dict,
    Iterable,
    Union,
)

from cytoolz import (
    merge,
)


class MissingReason:
    def __init__(self, reason):
        self.reason = reason

    def __str__(self, reason):
        return "Key is missing because it was {}".format(self.reason)


NEVER_INSERTED = MissingReason("never inserted")
DELETED = MissingReason("deleted")


class DiffMissingError(KeyError):
    def __init__(self, missing_key: bytes, reason: MissingReason) -> None:
        self.reason = reason
        super().__init__(missing_key, reason)

    def is_deleted(self):
        return self.reason == DELETED


class DBDiffTracker(MutableMapping):
    """
    Recorded changes to a :class:`~evm.db.BaseDB`
    """
    def __init__(self):
        self._changes = {}  # type: Dict[bytes, Union[bytes, DiffMissingError]]

    def __contains__(self, key):
        result = self._changes.get(key, NEVER_INSERTED)
        return result not in (DELETED, NEVER_INSERTED)

    def __getitem__(self, key):
        result = self._changes.get(key, NEVER_INSERTED)
        if result in (DELETED, NEVER_INSERTED):
            raise DiffMissingError(key, result)
        else:
            return result

    def __setitem__(self, key, value):
        self._changes[key] = value

    def __delitem__(self, key):
        # The diff does not have access to any underlying db,
        # so it cannot check if the key exists before deleting.
        self._changes[key] = DELETED

    def __iter__(self):
        raise NotImplementedError(
            "Cannot iterate through changes, use diff().apply_to(db) to update a database"
        )

    def __len__(self):
        return len(self._changes)

    def diff(self):
        return DBDiff(self)


class DBDiff(Mapping):
    _changes = None  # type: Dict[bytes, Union[bytes, DiffMissingError]]

    def __init__(self, tracker: DBDiffTracker = None) -> None:
        if tracker is None:
            self._changes = {}
        else:
            self._changes = tracker._changes

    def __getitem__(self, key):
        result = self._changes.get(key, NEVER_INSERTED)
        if result in (DELETED, NEVER_INSERTED):
            raise DiffMissingError(key, result)
        else:
            return result

    def __iter__(self):
        raise NotImplementedError(
            "Cannot iterate through changes, use apply_to(db) to update a database"
        )

    def __len__(self):
        return len(self._changes)

    def apply_to(self, db, apply_deletes=True):
        for key, value in self._changes.items():
            if value is DELETED and apply_deletes:
                try:
                    del db[key]
                except KeyError:
                    pass
            else:
                db[key] = value

    @classmethod
    def join(cls, diffs: Iterable['DBDiff']) -> 'DBDiff':
        new_diff = cls()
        new_diff._changes = merge(diff._changes for diff in diffs)
        return new_diff
