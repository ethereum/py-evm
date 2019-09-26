from typing import Any

import rlp

from p2p.abc import MessageAPI


class Message(MessageAPI):
    def __init__(self, header: bytes, body: bytes):
        self.header = header
        self.body = body

    @property
    def command_id(self) -> int:
        return rlp.decode(self.body[:1], sedes=rlp.sedes.big_endian_int)

    def __eq__(self, other: Any) -> bool:
        if type(other) is not type(self):
            return False
        return self.header == other.header and self.body == other.body

    def __str__(self) -> str:
        return f"Message(header={self.header.hex()}, body={self.body.hex()})"

    def __repr__(self) -> str:
        return f"Message(header={self.header}, body={self.body})"
