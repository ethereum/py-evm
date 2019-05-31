import pathlib

from p2p.exceptions import HandshakeFailure
from p2p.tracking.connection import register_error

from trinity.constants import BLACKLIST_SECONDS_WRONG_NETWORK_OR_GENESIS


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


class AttestationNotFound(BaseTrinityError):
    """
    Raised when attestion with given attestation root does not exist.
    """
    pass


class WrongNetworkFailure(HandshakeFailure):
    """
    Disconnected from the peer because it's on a different network than we're on
    """
    pass


register_error(WrongNetworkFailure, BLACKLIST_SECONDS_WRONG_NETWORK_OR_GENESIS)


class WrongGenesisFailure(HandshakeFailure):
    """
    Disconnected from the peer because it has a different genesis than we do
    """
    pass


register_error(WrongGenesisFailure, BLACKLIST_SECONDS_WRONG_NETWORK_OR_GENESIS)
