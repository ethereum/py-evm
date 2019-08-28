from typing import (
    cast,
    Any,
    Dict,
)

from eth_utils import ValidationError
from eth_utils.toolz import assoc

import rlp
from rlp import sedes

from p2p.abc import TransportAPI
from p2p.constants import P2P_PROTOCOL_COMMAND_LENGTH
from p2p.disconnect import DisconnectReason as _DisconnectReason
from p2p.exceptions import MalformedMessage
from p2p.typing import Capabilities, Payload

from p2p.protocol import (
    Command,
    Protocol,
)


class Hello(Command):
    _cmd_id = 0
    decode_strict = False
    structure = (
        ('version', sedes.big_endian_int),
        ('client_version_string', sedes.text),
        ('capabilities', sedes.CountableList(sedes.List([sedes.text, sedes.big_endian_int]))),
        ('listen_port', sedes.big_endian_int),
        ('remote_pubkey', sedes.binary)
    )

    def decompress_payload(self, raw_payload: bytes) -> bytes:
        # The `Hello` command doesn't support snappy compression
        return raw_payload

    def compress_payload(self, raw_payload: bytes) -> bytes:
        # The `Hello` command doesn't support snappy compression
        return raw_payload


class Disconnect(Command):
    _cmd_id = 1
    structure = (('reason', sedes.big_endian_int),)

    def get_reason_name(self, reason_id: int) -> str:
        try:
            return _DisconnectReason(reason_id).name
        except ValueError:
            return "unknown reason"

    def decode(self, data: bytes) -> Payload:
        try:
            raw_decoded = cast(Dict[str, int], super().decode(data))
        except rlp.exceptions.ListDeserializationError:
            self.logger.warning("Malformed Disconnect message: %s", data)
            raise MalformedMessage(f"Malformed Disconnect message: {data}")
        return assoc(raw_decoded, 'reason_name', self.get_reason_name(raw_decoded['reason']))


class Ping(Command):
    _cmd_id = 2
    structure = ()


class Pong(Command):
    _cmd_id = 3
    structure = ()


class BaseP2PProtocol(Protocol):
    name = 'p2p'
    _commands = (Hello, Ping, Pong, Disconnect)
    cmd_length = P2P_PROTOCOL_COMMAND_LENGTH

    def __init__(self, transport: TransportAPI, cmd_id_offset: int, snappy_support: bool) -> None:
        if cmd_id_offset != 0:
            raise TypeError(
                f"The base `p2p` protocol **must** have a cmd_id_offset of 0. "
                f"Got `{cmd_id_offset}`"
            )
        super().__init__(transport, cmd_id_offset, snappy_support)

    def send_handshake(
            self,
            client_version_string: str,
            capabilities: Capabilities,
            listen_port: int,
            p2p_version: int) -> None:
        if p2p_version != self.version:
            raise ValidationError(
                f"P2P version mismatch.  Handshake parameters set as "
                f"v{p2p_version} but protocol class has v{self.version}"
            )
        self.send_hello(
            version=self.version,
            client_version_string=client_version_string,
            capabilities=capabilities,
            listen_port=listen_port,
            remote_pubkey=self.transport.public_key.to_bytes(),
        )

    def send_hello(self,
                   version: int,
                   client_version_string: str,
                   capabilities: Capabilities,
                   listen_port: int,
                   remote_pubkey: bytes) -> None:
        data = dict(version=version,
                    client_version_string=client_version_string,
                    capabilities=capabilities,
                    listen_port=listen_port,
                    remote_pubkey=remote_pubkey)
        header, body = Hello(self.cmd_id_offset, self.snappy_support).encode(data)
        self.transport.send(header, body)

    def send_disconnect(self, reason: _DisconnectReason) -> None:
        msg: Dict[str, Any] = {"reason": reason.value}
        header, body = Disconnect(
            self.cmd_id_offset,
            self.snappy_support
        ).encode(msg)
        self.transport.send(header, body)

    def send_ping(self) -> None:
        header, body = Ping(self.cmd_id_offset, self.snappy_support).encode({})
        self.transport.send(header, body)

    def send_pong(self) -> None:
        header, body = Pong(self.cmd_id_offset, self.snappy_support).encode({})
        self.transport.send(header, body)


class P2PProtocolV4(BaseP2PProtocol):
    version = 4

    def __init__(self, transport: TransportAPI, cmd_id_offset: int, snappy_support: bool) -> None:
        if snappy_support is True:
            raise TypeError(
                f"Snappy support is not supported before version 5 of the p2p "
                f"protocol.  Currently using version `{self.version}`"
            )
        super().__init__(transport, cmd_id_offset=cmd_id_offset, snappy_support=False)


class P2PProtocol(BaseP2PProtocol):
    version = 5
