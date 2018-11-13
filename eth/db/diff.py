from collections.abc import (
    Mapping,
    MutableMapping,
)
from typing import (
    Dict,
    Iterable,
    Union,
    TYPE_CHECKING,
)

from eth.db.backends.base import BaseDB

if TYPE_CHECKING:
    ABC_Mutable_Mapping = MutableMapping[bytes, Union[bytes, 'MissingReason']]
    ABC_Mapping = Mapping[bytes, Union[bytes, 'MissingReason']]
else:
    ABC_Mutable_Mapping = MutableMapping
    ABC_Mapping = Mapping


class MissingReason:
    def __init__(self, reason: str) -> None:
        self.reason = reason

    def __str__(self, reason: str) -> str:      # type: ignore
        # Ignoring mypy type here because the function signature
        # has been overwritten from the traditional `def __str__(self): ...`
        return "Key is missing because it was {}".format(self.reason)


NEVER_INSERTED = MissingReason("never inserted")
DELETED = MissingReason("deleted")


class DiffMissingError(KeyError):
    """
    Raised when trying to access a missing key/value pair in a :class:`DBDiff`
    or :class:`DBDiffTracker`.

    Use :attr:`is_deleted` to check if the value is missing because it was
    deleted, or simply because it was never updated.
    """
    def __init__(self, missing_key: bytes, reason: MissingReason) -> None:
        self.reason = reason
        super().__init__(missing_key, reason)

    @property
    def is_deleted(self) -> bool:
        return self.reason == DELETED


class DBDiffTracker(ABC_Mutable_Mapping):
    """
    Records changes to a :class:`~eth.db.BaseDB`

    If no value is available for a key, it could be for one of two reasons:
    - the key was never updated during tracking
    - the key was deleted at some point

    When getting a value, a special subtype of KeyError is raised on failure.
    The exception, :class:`DiffMissingError`, can be used to check if the value
    was deleted, or never present, using :meth:`DiffMissingError.is_deleted`.

    When it's time to take the tracked changes and write them to your database,
    get the :class:`DBDiff` with :meth:`DBDiffTracker.diff` and use the attached methods.
    """
    def __init__(self) -> None:
        self._changes = {}  # type: Dict[bytes, Union[bytes, MissingReason]]

    def __contains__(self, key: bytes) -> bool:  # type: ignore # Breaks LSP
        result = self._changes.get(key, NEVER_INSERTED)
        return result not in (DELETED, NEVER_INSERTED)

    def __getitem__(self, key: bytes) -> bytes:
        result = self._changes.get(key, NEVER_INSERTED)
        if result in (DELETED, NEVER_INSERTED):
            raise DiffMissingError(key, result)  # type: ignore # ignore over cast for perf reasons
        else:
            return result  # type: ignore # ignore over cast for perf reasons

    def __setitem__(self, key: bytes, value: Union[bytes, MissingReason]) -> None:
        self._changes[key] = value

    def __delitem__(self, key: bytes) -> None:
        # The diff does not have access to any underlying db,
        # so it cannot check if the key exists before deleting.
        self._changes[key] = DELETED

    def __iter__(self) -> None:
        raise NotImplementedError(
            "Cannot iterate through changes, use diff().apply_to(db) to update a database"
        )

    def __len__(self) -> int:
        return len(self._changes)

    def diff(self) -> 'DBDiff':
        return DBDiff(dict(self._changes))


class DBDiff(ABC_Mapping):
    """
    DBDiff is a read-only view of the updates/inserts and deletes
    generated when tracking changes with :class:`DBDiffTracker`.

    The primary usage is to apply these changes to your underlying
    database with :meth:`apply_to`.
    """
    _changes = None  # type: Dict[bytes, Union[bytes, MissingReason]]

    def __init__(self, changes: Dict[bytes, Union[bytes, MissingReason]] = None) -> None:
        if changes is None:
            self._changes = {}
        else:
            self._changes = changes

    def __getitem__(self, key: bytes) -> bytes:
        result = self._changes.get(key, NEVER_INSERTED)
        if result in (DELETED, NEVER_INSERTED):
            raise DiffMissingError(key, result)  # type: ignore # ignore over cast for perf reasons
        else:
            return result  # type: ignore # ignore over cast for perf reasons

    def __iter__(self) -> None:
        raise NotImplementedError(
            "Cannot iterate through changes, use apply_to(db) to update a database"
        )

    def __len__(self) -> int:
        return len(self._changes)

    def apply_to(self,
                 db: Union[BaseDB, ABC_Mutable_Mapping],
                 apply_deletes: bool = True) -> None:
        """
        Apply the changes in this diff to the given database.
        You may choose to opt out of deleting any underlying keys.

        :param apply_deletes: whether the pending deletes should be
            applied to the database
        """
        for key, value in self._changes.items():
            if value is DELETED:
                if apply_deletes:
                    try:
                        del db[key]
                    except KeyError:
                        pass
                else:
                    pass
            else:
                db[key] = value  # type: ignore # ignore over cast for perf reasons

    @classmethod
    def join(cls, diffs: Iterable['DBDiff']) -> 'DBDiff':
        """
        Join several DBDiff objects into a single DBDiff object.

        In case of a conflict, changes in diffs that come later
        in ``diffs`` will overwrite changes from earlier changes.
        """
        tracker = DBDiffTracker()
        for diff in diffs:
            diff.apply_to(tracker)
        return tracker.diff()
