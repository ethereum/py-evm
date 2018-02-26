import enum
from typing import cast, Dict

from cytoolz import assoc

from rlp import sedes

from p2p.protocol import (
    Command,
    Protocol,
    _DecodedMsgType,
)

from .constants import (
    CLIENT_VERSION_STRING,
)


class Hello(Command):
    _cmd_id = 0
    decode_strict = False
    structure = [
        ('version', sedes.big_endian_int),
        ('client_version_string', sedes.binary),
        ('capabilities', sedes.CountableList(sedes.List([sedes.binary, sedes.big_endian_int]))),
        ('listen_port', sedes.big_endian_int),
        ('remote_pubkey', sedes.binary)
    ]


@enum.unique
class DisconnectReason(enum.Enum):
    disconnect_requested = 0
    tcp_sub_system_error = 1
    bad_protocol = 2
    useless_peer = 3
    too_many_peers = 4
    already_connected = 5
    incompatible_p2p_version = 6
    null_node_identity_received = 7
    client_quitting = 8
    unexpected_identity = 9
    connected_to_self = 10
    timeout = 11
    subprotocol_error = 12
    other = 16


class Disconnect(Command):
    _cmd_id = 1
    structure = [('reason', sedes.big_endian_int)]

    def get_reason_name(self, reason_id: int) -> str:
        try:
            return DisconnectReason(reason_id).name
        except ValueError:
            return "unknown reason"

    def decode(self, data: bytes) -> _DecodedMsgType:
        raw_decoded = cast(Dict[str, int], super(Disconnect, self).decode(data))
        return assoc(raw_decoded, 'reason_name', self.get_reason_name(raw_decoded['reason']))


class Ping(Command):
    _cmd_id = 2


class Pong(Command):
    _cmd_id = 3


class P2PProtocol(Protocol):
    name = b'p2p'
    version = 4
    _commands = [Hello, Ping, Pong, Disconnect]
    cmd_length = 16

    def __init__(self, peer):
        # For the base protocol the cmd_id_offset is always 0.
        super(P2PProtocol, self).__init__(peer, cmd_id_offset=0)

    def send_handshake(self):
        data = dict(version=self.version,
                    client_version_string=CLIENT_VERSION_STRING,
                    capabilities=self.peer.capabilities,
                    listen_port=self.peer.listen_port,
                    remote_pubkey=self.peer.privkey.public_key.to_bytes())
        header, body = Hello(self).encode(data)
        self.send(header, body)

    def send_disconnect(self, reason):
        header, body = Disconnect(self).encode(dict(reason=reason))
        self.send(header, body)

    def send_pong(self):
        header, body = Pong(self).encode({})
        self.send(header, body)
