from typing import cast, Any, Dict

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

from .proto import ETHProtocol, ETHHandshakeParams
from .commands import Status


class ETHHandshakeReceipt(HandshakeReceipt):
    handshake_params: ETHHandshakeParams

    def __init__(self, protocol: ETHProtocol, handshake_params: ETHHandshakeParams) -> None:
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
    handshake_params: ETHHandshakeParams

    def __init__(self, handshake_params: ETHHandshakeParams) -> None:
        self.handshake_params = handshake_params

    async def do_handshake(self,
                           multiplexer: MultiplexerAPI,
                           protocol: ProtocolAPI) -> ETHHandshakeReceipt:
        """Perform the handshake for the sub-protocol agreed with the remote peer.

        Raises HandshakeFailure if the handshake is not successful.
        """
        protocol = cast(ETHProtocol, protocol)
        protocol.send_handshake(self.handshake_params)

        async for cmd, msg in multiplexer.stream_protocol_messages(protocol):
            if not isinstance(cmd, Status):
                raise HandshakeFailure(f"Expected a ETH Status msg, got {cmd}, disconnecting")

            msg = cast(Dict[str, Any], msg)

            remote_params = ETHHandshakeParams(
                version=msg['protocol_version'],
                network_id=msg['network_id'],
                total_difficulty=msg['td'],
                head_hash=msg['best_hash'],
                genesis_hash=msg['genesis_hash'],
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
