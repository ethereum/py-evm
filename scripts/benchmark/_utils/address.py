import random
from typing import (
    Tuple,
)

from eth_keys import (
    keys,
)
from eth_keys.datatypes import (
    PrivateKey,
    PublicKey,
)
from eth_typing import (
    Address,
)
from eth_utils import (
    int_to_big_endian,
)

from eth._utils.padding import (
    pad32,
)


def generate_random_keypair_and_address() -> Tuple[PrivateKey, PublicKey, Address]:
    priv_key = keys.PrivateKey(pad32(int_to_big_endian(random.getrandbits(8 * 32))))
    return (
        priv_key,
        priv_key.public_key,
        Address(priv_key.public_key.to_canonical_address()),
    )


def generate_random_address() -> Address:
    private_key, public_key, address = generate_random_keypair_and_address()
    return address
