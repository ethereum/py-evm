from typing import (
    Callable,
    NamedTuple,
    NewType,
)


AES128Key = NewType("AES128Key", bytes)
Nonce = NewType("Nonce", bytes)
IDNonce = NewType("IDNonce", bytes)
Tag = NewType("Tag", bytes)

RandomBytesFn = Callable[[int], bytes]  # function that returns a number of random bytes
NodeID = NewType("NodeID", bytes)


class SessionKeys(NamedTuple):
    initiator_key: AES128Key
    recipient_key: AES128Key
    auth_response_key: AES128Key
