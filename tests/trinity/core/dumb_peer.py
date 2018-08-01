from p2p import protocol

from trinity.protocol.eth.peer import (
    ETHPeer,
)


class DumbPeer(ETHPeer):
    async def send_sub_proto_handshake(self):
        pass

    async def process_sub_proto_handshake(
            self, cmd: protocol.Command, msg: protocol._DecodedMsgType) -> None:
        pass

    async def do_sub_proto_handshake(self):
        pass
