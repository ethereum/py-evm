from typing import (
    cast,
    Type,
    Union,
)

from cached_property import cached_property

from eth_typing import BlockNumber, Hash32
from eth_utils import encode_hex

from p2p.abc import MultiplexerAPI, ProtocolAPI
from p2p.exceptions import (
    HandshakeFailure,
)
from p2p.handshake import Handshaker
from p2p.receipt import HandshakeReceipt

from trinity.exceptions import WrongGenesisFailure, WrongNetworkFailure

from .commands import StatusV1, StatusV2
from .payloads import StatusPayload
from .proto import LESProtocolV1, LESProtocolV2

AnyLESProtocol = Union[LESProtocolV1, LESProtocolV2]
AnyLESProtocolClass = Union[Type[LESProtocolV1], Type[LESProtocolV2]]


class LESHandshakeReceipt(HandshakeReceipt):
    handshake_params: StatusPayload

    def __init__(self,
                 protocol: AnyLESProtocol,
                 handshake_params: StatusPayload,
                 ) -> None:
        super().__init__(protocol)
        self.handshake_params = handshake_params

    @cached_property
    def network_id(self) -> int:
        return self.handshake_params.network_id

    @cached_property
    def head_td(self) -> int:
        return self.handshake_params.head_td

    @cached_property
    def head_hash(self) -> Hash32:
        return self.handshake_params.head_hash

    @cached_property
    def head_number(self) -> BlockNumber:
        return self.handshake_params.head_number

    @cached_property
    def genesis_hash(self) -> Hash32:
        return self.handshake_params.genesis_hash


class BaseLESHandshaker(Handshaker):
    handshake_params: StatusPayload

    def __init__(self, handshake_params: StatusPayload) -> None:
        if handshake_params.version != self.protocol_class.version:
            raise Exception("DID NOT MATCH")
        self.handshake_params = handshake_params

    async def do_handshake(self,
                           multiplexer: MultiplexerAPI,
                           protocol: ProtocolAPI) -> LESHandshakeReceipt:
        """Perform the handshake for the sub-protocol agreed with the remote peer.

        Raises HandshakeFailure if the handshake is not successful.
        """
        protocol = cast(AnyLESProtocol, protocol)
        protocol.send(protocol.status_command_type(self.handshake_params))

        async for cmd in multiplexer.stream_protocol_messages(protocol):
            if not isinstance(cmd, (StatusV1, StatusV2)):
                raise HandshakeFailure(f"Expected a LES Status msg, got {cmd}, disconnecting")

            if cmd.payload.network_id != self.handshake_params.network_id:
                raise WrongNetworkFailure(
                    f"{multiplexer.remote} network "
                    f"({cmd.payload.network_id}) does not match ours "
                    f"({self.handshake_params.network_id}), disconnecting"
                )

            if cmd.payload.genesis_hash != self.handshake_params.genesis_hash:
                raise WrongGenesisFailure(
                    f"{multiplexer.remote} genesis "
                    f"({encode_hex(cmd.payload.genesis_hash)}) does "
                    f"not match ours "
                    f"({encode_hex(self.handshake_params.genesis_hash)}), "
                    f"disconnecting"
                )

            # Eventually we might want to keep connections to peers where we
            # are the only side serving data, but right now both our chain
            # syncer and the Peer.boot() method expect the remote to reply to
            # header requests, so if they don't we simply disconnect here.
            if cmd.payload.serve_headers is False:
                raise HandshakeFailure(f"{multiplexer.remote} doesn't serve headers, disconnecting")

            receipt = LESHandshakeReceipt(protocol, cmd.payload)
            break
        else:
            raise HandshakeFailure("Message stream exited before finishing handshake")

        return receipt


class LESV1Handshaker(BaseLESHandshaker):
    status_command_type = StatusV1
    protocol_class = LESProtocolV1


class LESV2Handshaker(BaseLESHandshaker):
    status_command_type = StatusV2
    protocol_class = LESProtocolV2
