from typing import Type

from p2p.abc import MultiplexerAPI, ProtocolAPI
from p2p.handshake import Handshaker, HandshakeReceipt


class NoopHandshaker(Handshaker):
    def __init__(self, protocol_class: Type[ProtocolAPI]) -> None:
        self.protocol_class = protocol_class

    async def do_handshake(self,
                           multiplexer: MultiplexerAPI,
                           protocol: ProtocolAPI) -> HandshakeReceipt:
        return HandshakeReceipt(protocol)
