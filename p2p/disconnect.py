import enum


@enum.unique
class DisconnectReason(enum.Enum):
    """More details at https://github.com/ethereum/wiki/wiki/%C3%90%CE%9EVp2p-Wire-Protocol#p2p"""
    DISCONNECT_REQUESTED = 0
    TCP_SUB_SYSTEM_ERROR = 1
    BAD_PROTOCOL = 2
    USELESS_PEER = 3
    TOO_MANY_PEERS = 4
    ALREADY_CONNECTED = 5
    INCOMPATIBLE_P2P_VERSION = 6
    NULL_NODE_IDENTITY_RECEIVED = 7
    CLIENT_QUITTING = 8
    UNEXPECTED_IDENTITY = 9
    CONNECTED_TO_SELF = 10
    TIMEOUT = 11
    SUBPROTOCOL_ERROR = 16
