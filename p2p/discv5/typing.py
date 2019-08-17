from typing import (
    NamedTuple,
    NewType,
    Optional,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from p2p.discv5.enr import (
        ENR,
    )
    from p2p.discv5.messages import (
        BaseMessage,
    )
    from p2p.discv5.packets import (
        AuthHeaderPacket,
    )


AES128Key = NewType("AES128Key", bytes)
Nonce = NewType("Nonce", bytes)
IDNonce = NewType("IDNonce", bytes)
Tag = NewType("Tag", bytes)

NodeID = NewType("NodeID", bytes)


class SessionKeys(NamedTuple):
    initiator_key: AES128Key
    recipient_key: AES128Key
    auth_response_key: AES128Key


class HandshakeResult(NamedTuple):
    session_keys: SessionKeys
    enr: Optional["ENR"]
    message: Optional["BaseMessage"]
    auth_header_packet: Optional["AuthHeaderPacket"]
