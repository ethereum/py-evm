from typing import Any

import rlp

from p2p.abc import MessageAPI


class Message(MessageAPI):
    def __init__(self, header: bytes, body: bytes):
        self.header = header
        self.body = body
        self.command_id = rlp.decode(self.body[:1], sedes=rlp.sedes.big_endian_int)
        self.encoded_payload = self.body[1:]

    def __eq__(self, other: Any) -> bool:
        if type(other) is not type(self):
            return False
        return self.header == other.header and self.body == other.body

    def __str__(self) -> str:
        return f"Message(header={self.header.hex()}, body={self.body.hex()})"

    def __repr__(self) -> str:
        return f"Message(header={self.header!r}, body={self.body!r})"
