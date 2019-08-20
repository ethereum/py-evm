from typing import cast

from eth_typing import Hash32
from eth_utils import encode_hex

from p2p.abc import MultiplexerAPI, ProtocolAPI
from p2p.exceptions import (
    HandshakeFailure,
)
from p2p.handshake import (
    HandshakeReceipt,
    Handshaker,
)

from .commands import (
    Status,
    StatusMessage,
)
from .proto import BCCProtocol, BCCHandshakeParams


class BCCHandshakeReceipt(HandshakeReceipt):
    handshake_params: BCCHandshakeParams

    def __init__(self, protocol: BCCProtocol, handshake_params: BCCHandshakeParams) -> None:
        super().__init__(protocol)
        self.handshake_params = handshake_params

    @property
    def genesis_root(self) -> Hash32:
        return self.handshake_params.genesis_root

    @property
    def network_id(self) -> int:
        return self.handshake_params.network_id


class BCCHandshaker(Handshaker):
    protocol_class = BCCProtocol
    handshake_params: BCCHandshakeParams

    def __init__(self, handshake_params: BCCHandshakeParams) -> None:
        self.handshake_params = handshake_params

    async def do_handshake(self,
                           multiplexer: MultiplexerAPI,
                           protocol: ProtocolAPI) -> BCCHandshakeReceipt:
        """Perform the handshake for the sub-protocol agreed with the remote peer.

        Raises HandshakeFailure if the handshake is not successful.
        """
        protocol = cast(BCCProtocol, protocol)
        protocol.send_handshake(self.handshake_params)

        async for cmd, msg in multiplexer.stream_protocol_messages(protocol):
            if not isinstance(cmd, Status):
                raise HandshakeFailure(f"Expected a BCC Status msg, got {cmd}, disconnecting")

            msg = cast(StatusMessage, msg)
            remote_params = BCCHandshakeParams(
                protocol_version=msg['protocol_version'],
                network_id=msg['network_id'],
                genesis_root=msg['genesis_root'],
                head_slot=msg['head_slot'],
            )

            if remote_params.network_id != self.handshake_params.network_id:
                raise HandshakeFailure(
                    f"{self} network ({remote_params.network_id}) does not match ours "
                    f"({self.handshake_params.network_id}), disconnecting"
                )
            if remote_params.genesis_root != self.handshake_params.genesis_root:
                raise HandshakeFailure(
                    f"{self} genesis ({encode_hex(remote_params.genesis_root)}) does not "
                    f"match ours ({encode_hex(self.handshake_params.genesis_root)}), disconnecting"
                )

            receipt = BCCHandshakeReceipt(protocol, remote_params)
            break
        else:
            raise HandshakeFailure("Message stream exited before finishing handshake")

        return receipt
