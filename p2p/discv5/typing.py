from typing import (
    Callable,
    NamedTuple,
    NewType,
)


AES128Key = NewType("AES128Key", bytes)
Nonce = NewType("Nonce", bytes)

RandomBytesFn = Callable[[int], bytes]  # function that returns a number of random bytes


class SessionKeys(NamedTuple):
    initiator_key: AES128Key
    recipient_key: AES128Key
    auth_response_key: AES128Key
