from rlp import sedes

from p2p import protocol
from p2p.peer import BasePeer


class DumbCommand(protocol.Command):
    _cmd_id = 0
    structure = [
        ('dumb_int', sedes.big_endian_int),
    ]


class DumbProtocol(protocol.Protocol):
    name = 'dumb'
    version = 1
    _commands = [DumbCommand]
    cmd_length = 1


class DumbPeer(BasePeer):
    _supported_sub_protocols = [DumbProtocol]
    sub_proto: DumbProtocol = None

    async def send_sub_proto_handshake(self):
        pass

    async def process_sub_proto_handshake(
            self, cmd: protocol.Command, msg: protocol._DecodedMsgType) -> None:
        pass

    async def do_sub_proto_handshake(self):
        pass
