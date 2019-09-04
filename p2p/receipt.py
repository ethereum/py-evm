from p2p.abc import (
    HandshakeReceiptAPI,
    ProtocolAPI,
)


class HandshakeReceipt(HandshakeReceiptAPI):
    """
    Data storage object for ephemeral data exchanged during protocol
    handshakes.
    """
    protocol: ProtocolAPI

    def __init__(self, protocol: ProtocolAPI) -> None:
        self.protocol = protocol
