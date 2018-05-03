class BaseP2PError(Exception):
    """
    The base class for all p2p errors.
    """
    pass


class DecryptionError(BaseP2PError):
    """
    Raised when a message could not be decrypted.
    """
    pass


class PeerConnectionLost(BaseP2PError):
    """
    Raised when the connection to a peer was lost.
    """
    pass


class HandshakeFailure(BaseP2PError):
    """
    Raised when the protocol handshake was unsuccessful.
    """
    pass


class UnknownProtocolCommand(BaseP2PError):
    """
    Raised when the received protocal command isn't known.
    """
    pass


class UnexpectedMessage(BaseP2PError):
    """
    Raised when the received message was unexpected.
    """
    pass


class UnreachablePeer(BaseP2PError):
    """
    Raised when a peer was unreachable.
    """
    pass


class EmptyGetBlockHeadersReply(BaseP2PError):
    """
    Raised when the received block headers were empty.
    """
    pass


class LESAnnouncementProcessingError(BaseP2PError):
    """
    Raised when an LES announcement could not be processed.
    """
    pass


class TooManyTimeouts(BaseP2PError):
    """
    Raised when too many timeouts occurred.
    """
    pass


class OperationCancelled(BaseP2PError):
    """
    Raised when an operation was cancelled.
    """
    pass


class NoMatchingPeerCapabilities(BaseP2PError):
    """
    Raised when no matching protocol between peers was found.
    """
    pass


class RemoteDisconnected(BaseP2PError):
    """
    Raised when a remote disconnected.
    """
    pass
