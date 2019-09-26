from typing import cast

from cached_property import cached_property

from eth_typing import Hash32
from eth_utils import encode_hex

from p2p.abc import MultiplexerAPI, ProtocolAPI
from p2p.exceptions import (
    HandshakeFailure,
)
from p2p.handshake import Handshaker
from p2p.receipt import HandshakeReceipt

from trinity.exceptions import WrongGenesisFailure, WrongNetworkFailure

from .commands import Status
from .payloads import StatusPayload
from .proto import ETHProtocol


class ETHHandshakeReceipt(HandshakeReceipt):
    handshake_params: StatusPayload

    def __init__(self, protocol: ETHProtocol, handshake_params: StatusPayload) -> None:
        super().__init__(protocol)
        self.handshake_params = handshake_params

    @cached_property
    def head_hash(self) -> Hash32:
        return self.handshake_params.head_hash

    @cached_property
    def genesis_hash(self) -> Hash32:
        return self.handshake_params.genesis_hash

    @cached_property
    def network_id(self) -> int:
        return self.handshake_params.network_id

    @cached_property
    def total_difficulty(self) -> int:
        return self.handshake_params.total_difficulty

    @cached_property
    def version(self) -> int:
        return self.handshake_params.version


class ETHHandshaker(Handshaker):
    protocol_class = ETHProtocol
    handshake_params: StatusPayload

    def __init__(self, handshake_params: StatusPayload) -> None:
        self.handshake_params = handshake_params

    async def do_handshake(self,
                           multiplexer: MultiplexerAPI,
                           protocol: ProtocolAPI) -> ETHHandshakeReceipt:
        """Perform the handshake for the sub-protocol agreed with the remote peer.

        Raises HandshakeFailure if the handshake is not successful.
        """
        protocol = cast(ETHProtocol, protocol)
        protocol.send(Status(self.handshake_params))

        async for cmd in multiplexer.stream_protocol_messages(protocol):
            if not isinstance(cmd, Status):
                raise HandshakeFailure(f"Expected a ETH Status msg, got {cmd}, disconnecting")

            remote_params = StatusPayload(
                version=cmd.payload.version,
                network_id=cmd.payload.network_id,
                total_difficulty=cmd.payload.total_difficulty,
                head_hash=cmd.payload.head_hash,
                genesis_hash=cmd.payload.genesis_hash,
            )
            receipt = ETHHandshakeReceipt(protocol, remote_params)

            if receipt.handshake_params.network_id != self.handshake_params.network_id:
                raise WrongNetworkFailure(
                    f"{multiplexer.remote} network "
                    f"({receipt.handshake_params.network_id}) does not match ours "
                    f"({self.handshake_params.network_id}), disconnecting"
                )

            if receipt.handshake_params.genesis_hash != self.handshake_params.genesis_hash:
                raise WrongGenesisFailure(
                    f"{multiplexer.remote} genesis "
                    f"({encode_hex(receipt.handshake_params.genesis_hash)}) does "
                    f"not match ours ({encode_hex(self.handshake_params.genesis_hash)}), "
                    f"disconnecting"
                )

            break
        else:
            raise HandshakeFailure("Message stream exited before finishing handshake")

        return receipt
