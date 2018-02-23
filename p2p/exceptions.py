class AuthenticationError(Exception):
    pass


class DecryptionError(Exception):
    pass


class PeerConnectionLost(Exception):
    pass


class HandshakeFailure(Exception):
    pass


class UnknownProtocolCommand(Exception):
    pass


class UnexpectedMessage(Exception):
    pass


class UnreachablePeer(Exception):
    pass


class EmptyGetBlockHeadersReply(Exception):
    pass


class LESAnnouncementProcessingError(Exception):
    pass


class TooManyTimeouts(Exception):
    pass


class PeerFinished(Exception):
    pass


class OperationCancelled(Exception):
    pass
