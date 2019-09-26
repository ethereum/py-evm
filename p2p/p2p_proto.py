import operator
from typing import (
    NamedTuple,
    Tuple,
)

import rlp

from eth_utils.toolz import compose

from p2p.abc import TransportAPI
from p2p.constants import DEVP2P_V4, DEVP2P_V5, P2P_PROTOCOL_COMMAND_LENGTH
from p2p.disconnect import DisconnectReason
from p2p.receipt import HandshakeReceipt
from p2p.typing import Capabilities

from p2p.commands import (
    BaseCommand,
    NoCompressionCodec,
    NoneSerializationCodec,
    RLPCodec,
)
from p2p.protocol import BaseProtocol


class HelloPayload(NamedTuple):
    version: int
    client_version_string: str
    capabilities: Tuple[Tuple[str, int], ...]
    listen_port: int
    remote_public_key: bytes


HELLO_STRUCTURE = rlp.sedes.List((
    # version
    rlp.sedes.big_endian_int,
    # client_version_string
    rlp.sedes.text,
    # capabilities
    rlp.sedes.CountableList(rlp.sedes.List([rlp.sedes.text, rlp.sedes.big_endian_int])),
    # listen_port
    rlp.sedes.big_endian_int,
    # remote_public_key
    rlp.sedes.binary,
), strict=False)


class Hello(BaseCommand[HelloPayload]):
    protocol_command_id = 0

    serialization_codec: RLPCodec[HelloPayload] = RLPCodec(
        HELLO_STRUCTURE,
        decode_strict=False,
        process_inbound_payload_fn=lambda args: HelloPayload(*args),
    )
    compression_codec = NoCompressionCodec()


DISCONNECT_STRUCTURE = rlp.sedes.List((rlp.sedes.big_endian_int,))


class Disconnect(BaseCommand[DisconnectReason]):
    protocol_command_id = 1
    serialization_codec = RLPCodec(
        sedes=DISCONNECT_STRUCTURE,
        process_outbound_payload_fn=compose(lambda v: (v,), operator.attrgetter('value')),
        process_inbound_payload_fn=compose(DisconnectReason, operator.itemgetter(0)),
    )


class Ping(BaseCommand[None]):
    protocol_command_id = 2
    serialization_codec = NoneSerializationCodec()


class Pong(BaseCommand[None]):
    protocol_command_id = 3
    serialization_codec = NoneSerializationCodec()


class BaseP2PProtocol(BaseProtocol):
    name = 'p2p'

    commands = (
        Hello,
        Disconnect,
        Ping,
        Pong,
    )
    command_length = P2P_PROTOCOL_COMMAND_LENGTH

    def __init__(self,
                 transport: TransportAPI,
                 command_id_offset: int,
                 snappy_support: bool) -> None:
        if command_id_offset != 0:
            raise TypeError("The `command_id_offset` for the `p2p` protocol must be 0")
        super().__init__(transport, command_id_offset, snappy_support)


class P2PProtocolV4(BaseP2PProtocol):
    version = DEVP2P_V4

    def __init__(self,
                 transport: TransportAPI,
                 command_id_offset: int,
                 snappy_support: bool) -> None:
        if snappy_support is True:
            raise TypeError(
                f"Snappy support is not supported before version 5 of the p2p "
                f"protocol.  Currently using version `{self.version}`"
            )
        super().__init__(transport, command_id_offset, snappy_support=False)


class P2PProtocolV5(BaseP2PProtocol):
    version = DEVP2P_V5


class DevP2PReceipt(HandshakeReceipt):
    """
    Record of the handshake data from the core `p2p` protocol handshake.
    """
    def __init__(self,
                 protocol: BaseP2PProtocol,
                 version: int,
                 client_version_string: str,
                 capabilities: Capabilities,
                 listen_port: int,
                 remote_public_key: bytes) -> None:
        super().__init__(protocol)
        self.version = version
        self.client_version_string = client_version_string
        self.capabilities = capabilities
        self.listen_port = listen_port
        self.remote_public_key = remote_public_key
