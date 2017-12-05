from typing import TYPE_CHECKING

# Workaround for import cycles caused by type annotations:
# http://mypy.readthedocs.io/en/latest/common_issues.html#import-cycles
if TYPE_CHECKING:
    from evm.p2p.p2p_proto import DisconnectReason  # noqa: F401


class AuthenticationError(Exception):
    pass


class DecryptionError(Exception):
    pass


class PeerConnectionLost(Exception):
    pass


class PeerDisconnected(Exception):
    pass


class UnknownProtocolCommand(Exception):
    pass


class UselessPeer(Exception):
    pass


class UnreachablePeer(Exception):
    pass


class EmptyGetBlockHeadersReply(Exception):
    pass


class LESAnnouncementProcessingError(Exception):
    pass


class TooManyTimeouts(Exception):
    pass


class StopRequested(Exception):
    pass


class HandshakeFailure(Exception):

    def __init__(self, reason: 'DisconnectReason') -> None:
        self.reason = reason

    def __str__(self):
        return self.reason.name
