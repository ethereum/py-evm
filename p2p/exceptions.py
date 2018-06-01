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


class MalformedMessage(BaseP2PError):
    """
    Raised when a p2p command is received with a malformed message
    """


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


class NoEligiblePeers(BaseP2PError):
    """
    Raised when none of our peers have the blocks we want.
    """
    pass


class EventLoopMismatch(BaseP2PError):
    """
    Raised when two different asyncio event loops are referenced, but must be equal
    """
    pass


class NoEligibleNodes(BaseP2PError):
    """
    Raised when there are no nodes which meet some filter criteria
    """
    pass


class BadAckMessage(BaseP2PError):
    """
    Raised when the ack message during a peer handshake is malformed
    """
    pass


class BadLESResponse(BaseP2PError):
    """
    Raised when the response to a LES request doesn't contain the data we asked for.
    """
    pass
