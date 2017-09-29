from rlp import sedes

from evm.p2p.constants import (
    CLIENT_VERSION_STRING,
)
from evm.p2p.protocol import (
    Command,
    Protocol,
)


class Hello(Command):
    _id = 0
    decode_strict = False
    structure = [
        ('version', sedes.big_endian_int),
        ('client_version_string', sedes.binary),
        ('capabilities', sedes.CountableList(sedes.List([sedes.binary, sedes.big_endian_int]))),
        ('listen_port', sedes.big_endian_int),
        ('remote_pubkey', sedes.binary)
    ]

    def handle(self, proto, data):
        hello = self.decode(data)
        return hello


class Disconnect(Command):
    _id = 1
    structure = [('reason', sedes.big_endian_int)]

    def get_reason_name(self, reason_id):
        names = {
            0: "disconnect requested",
            1: "tcp sub system error",
            2: "bad protocol",
            3: "useless peer",
            4: "too many peers",
            5: "already connected",
            6: "incompatibel p2p version",
            7: "null node identity received",
            8: "client quitting",
            9: "unexpected identity",
            10: "connected to self",
            11: "timeout",
            12: "subprotocol error",
            16: "other",
        }
        if reason_id in names:
            return names[reason_id]
        return "unknown reason"

    def handle(self, proto, data):
        decoded = self.decode(data)
        reason_name = self.get_reason_name(decoded['reason'])
        proto.logger.debug(
            "Peer {} disconnected; reason given: {}".format(proto.peer.remote, reason_name))
        proto.peer.stop()
        return decoded


class Ping(Command):
    _id = 2

    def handle(self, proto, data):
        proto.send_pong()
        return None


class Pong(Command):
    _id = 3

    def handle(self, proto, data):
        return None


class P2PProtocol(Protocol):
    name = b'p2p'
    version = 4
    _commands = [Hello, Ping, Pong, Disconnect]
    cmd_length = 16

    def __init__(self, peer):
        # For the base protocol the cmd_id_offset is always 0.
        super(P2PProtocol, self).__init__(peer, cmd_id_offset=0)

    def send_pong(self):
        header, body = Pong(self.cmd_id_offset).encode({})
        self.send(header, body)

    def get_hello_message(self):
        data = dict(version=self.version,
                    client_version_string=CLIENT_VERSION_STRING,
                    capabilities=self.peer.capabilities,
                    listen_port=self.peer.listen_port,
                    remote_pubkey=self.peer.privkey.public_key.to_bytes())
        return Hello(self.cmd_id_offset).encode(data)
