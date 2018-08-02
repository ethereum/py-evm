import random
from typing import (
    Tuple,
    NamedTuple,
)
from web3 import (
    Web3,
)
from eth.utils.padding import (
    pad32,
)

from eth_keys import (
    keys
)
from eth_keys.datatypes import (
    PrivateKey,
    PublicKey
)

from eth_utils import (
    int_to_big_endian,
    decode_hex,
)

from eth_typing import (
    Address
)

random.seed(12)

class Account(NamedTuple):
    private_key: bytes
    address: Address
    checksum_address: str

FIRST_ADDRESS_PRIVATE_KEY = keys.PrivateKey(
    decode_hex('0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8')
)
FIRST_ADDRESS = Address(FIRST_ADDRESS_PRIVATE_KEY.public_key.to_canonical_address())
FIRST_ADDRESS_CHECKSUM = Web3.toChecksumAddress(FIRST_ADDRESS)

SECOND_ADDRESS_PRIVATE_KEY = keys.PrivateKey(
    decode_hex('0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d0')
)
SECOND_ADDRESS = Address(SECOND_ADDRESS_PRIVATE_KEY.public_key.to_canonical_address())
SECOND_ADDRESS_CHECKSUM = Web3.toChecksumAddress(SECOND_ADDRESS)

SECOND_ACCOUNT = Account(
    private_key=SECOND_ADDRESS_PRIVATE_KEY,
    address=SECOND_ADDRESS,
    checksum_address=SECOND_ADDRESS_CHECKSUM
)
FIRST_ACCOUNT = Account(
    private_key=FIRST_ADDRESS_PRIVATE_KEY,
    address=FIRST_ADDRESS,
    checksum_address=FIRST_ADDRESS_CHECKSUM
)

def generate_random_keypair_and_address() -> Tuple[PrivateKey, PublicKey, Address]:
    priv_key = keys.PrivateKey(pad32(int_to_big_endian(random.getrandbits(8 * 32))))
    return priv_key, priv_key.public_key, Address(priv_key.public_key.to_canonical_address())


def generate_random_address() -> Address:
    private_key, public_key, address = generate_random_keypair_and_address()
    return address
