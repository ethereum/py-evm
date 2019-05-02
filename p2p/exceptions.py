from typing import (
    Any
)


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


class IneligiblePeer(BaseP2PError):
    """
    Raised when a peer is not a valid connection candidate.
    """
    pass


class HandshakeFailure(BaseP2PError):
    """
    Raised when the protocol handshake was unsuccessful.
    """
    pass


class WrongNetworkFailure(HandshakeFailure):
    """
    Disconnected from the peer because it's on a different network than we're on
    """
    pass


class WrongGenesisFailure(HandshakeFailure):
    """
    Disconnected from the peer because it has a different genesis than we do
    """
    pass


class TooManyPeersFailure(HandshakeFailure):
    """
    The remote disconnected from us because it has too many peers
    """
    pass


class MalformedMessage(BaseP2PError):
    """
    Raised when a p2p command is received with a malformed message
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


class RemoteDisconnected(BaseP2PError):
    """
    Raised when a remote disconnected.
    """
    pass


class NoConnectedPeers(BaseP2PError):
    """
    Raised when we are not connected to any peers.
    """
    pass


class NoEligiblePeers(BaseP2PError):
    """
    Raised when none of our peers have the data we want.
    """
    pass


class NoIdlePeers(BaseP2PError):
    """
    Raised when none of our peers is idle and can be used for data requests.
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

    The peer can be treated as violating protocol. Often, the repurcussion should be
    disconnection and blacklisting.
    """
    pass


class NoInternalAddressMatchesDevice(BaseP2PError):
    """
    Raised when no internal IP address matches the UPnP device that is being configured.
    """
    def __init__(self, *args: Any, device_hostname: str=None) -> None:
        super().__init__(*args)
        self.device_hostname = device_hostname


class AlreadyWaitingDiscoveryResponse(BaseP2PError):
    """
    Raised when we are already waiting for a discovery response from a given remote.
    """
    pass


class UnableToGetDiscV5Ticket(BaseP2PError):
    """
    Raised when we're unable to get a discv5 ticket from a remote peer.
    """
    pass
