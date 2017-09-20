from rlp import sedes

from evm.p2p.constants import (
    CLIENT_VERSION_STRING,
)
from evm.p2p.protocol import (
    Command,
    Protocol,
)


class Hello(Command):
    id = 0
    decode_strict = False
    structure = [
        ('version', sedes.big_endian_int),
        ('client_version_string', sedes.binary),
        ('capabilities', sedes.CountableList(sedes.List([sedes.binary, sedes.big_endian_int]))),
        ('listen_port', sedes.big_endian_int),
        ('remote_pubkey', sedes.binary)
    ]

    @classmethod
    def handle(cls, proto, data):
        hello = cls.decode(data)
        return hello


class Disconnect(Command):
    id = 1
    structure = [('reason', sedes.big_endian_int)]

    @classmethod
    def get_reason_name(cls, reason_id):
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

    @classmethod
    def handle(cls, proto, data):
        decoded = cls.decode(data)
        reason_name = cls.get_reason_name(decoded['reason'])
        proto.logger.debug(
            "Peer {} disconnected; reason given: {}".format(proto.peer.remote, reason_name))
        proto.peer.stop()
        return decoded


class Ping(Command):
    id = 2

    @classmethod
    def handle(cls, proto, data):
        header, body = Pong.encode({})
        proto.send(header, body)
        return None


class Pong(Command):
    id = 3

    @classmethod
    def handle(cls, proto, data):
        return None


class P2PProtocol(Protocol):
    name = b'p2p'
    version = 4
    commands = [Hello, Ping, Pong, Disconnect]
    cmd_length = 16

    def get_hello_message(self):
        data = dict(version=self.version,
                    client_version_string=CLIENT_VERSION_STRING,
                    capabilities=self.peer.capabilities,
                    listen_port=self.peer.listen_port,
                    remote_pubkey=self.peer.privkey.public_key.to_bytes())
        return Hello.encode(data)
