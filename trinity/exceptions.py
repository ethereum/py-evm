import pathlib


class BaseTrinityError(Exception):
    """
    The base class for all Trinity errors.
    """
    pass


class AmbigiousFileSystem(BaseTrinityError):
    """
    Raised when the file system paths are unclear
    """
    pass


class MissingPath(BaseTrinityError):
    """
    Raised when an expected path is missing
    """
    def __init__(self, msg: str, path: pathlib.Path) -> None:
        super().__init__(msg)
        self.path = path


class AlreadyWaiting(BaseTrinityError):
    """
    Raised when an attempt is made to wait for a certain message type from a
    peer when there is already an active wait for that message type.
    """
    pass


class SyncRequestAlreadyProcessed(BaseTrinityError):
    """
    Raised when a trie SyncRequest has already been processed.
    """
    pass


class OversizeObject(BaseTrinityError):
    """
    Raised when an object is bigger than comfortably fits in memory.
    """
    pass


class DAOForkCheckFailure(BaseTrinityError):
    """
    Raised when the DAO fork check with a certain peer is unsuccessful.
    """
    pass


class BadDatabaseError(BaseTrinityError):
    """
    The local network database is not in the expected format
     - empty
     - wrong schema version
     - missing tables
    """
    pass
