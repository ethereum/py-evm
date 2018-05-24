from typing import (
    Any,
    Optional,
    Type,
    Union
)

from .datatypes import (
    LazyBackend,
)

import datatypes


class KeyAPI(LazyBackend):
    PublicKey: Type[datatypes.PublicKey] = ...
    PrivateKey: Type[datatypes.PrivateKey] = ...
    Signature: Type[datatypes.Signature] = ...
    def ecdsa_sign(self, message_hash: bytes, private_key: Union[datatypes.PrivateKey, bytes]) -> Optional[datatypes.Signature]: ...
    def ecdsa_verify(self, message_hash: bytes, signature: Union[datatypes.Signature, bytes], public_key: Union[datatypes.PublicKey, bytes]) -> Optional[bool]: ...
    def ecdsa_recover(self, message_hash: bytes, signature: Union[datatypes.Signature, bytes]) -> Optional[datatypes.PublicKey]: ...
    def private_key_to_public_key(self, private_key: datatypes.PrivateKey) -> datatypes.PublicKey: ...

lazy_key_api: KeyAPI
