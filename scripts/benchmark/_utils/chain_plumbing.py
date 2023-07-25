from typing import (
    Any,
    Dict,
    Iterable,
    Tuple,
)

from eth_keys import (
    keys,
)
from eth_typing import (
    Address,
)
from eth_utils import (
    decode_hex,
    to_wei,
)

from eth import (
    constants,
)
from eth.chains.mainnet import (
    BaseMainnetChain,
)

ALL_VM = [vm for _, vm in BaseMainnetChain.vm_configuration]

FUNDED_ADDRESS_PRIVATE_KEY = keys.PrivateKey(
    decode_hex("0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8")
)

FUNDED_ADDRESS = Address(FUNDED_ADDRESS_PRIVATE_KEY.public_key.to_canonical_address())

DEFAULT_INITIAL_BALANCE = to_wei(10000, "ether")

SECOND_ADDRESS_PRIVATE_KEY = keys.PrivateKey(
    decode_hex("0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d0")
)

SECOND_ADDRESS = Address(SECOND_ADDRESS_PRIVATE_KEY.public_key.to_canonical_address())

GENESIS_PARAMS = {
    "coinbase": constants.ZERO_ADDRESS,
    "transaction_root": constants.BLANK_ROOT_HASH,
    "receipt_root": constants.BLANK_ROOT_HASH,
    "difficulty": 1,
    "gas_limit": 3141592,
    "extra_data": constants.GENESIS_EXTRA_DATA,
    "nonce": constants.GENESIS_NONCE,
}

DEFAULT_GENESIS_STATE = [
    (
        FUNDED_ADDRESS,
        {
            "balance": DEFAULT_INITIAL_BALANCE,
            "code": b"",
        },
    ),
    (
        SECOND_ADDRESS,
        {
            "balance": DEFAULT_INITIAL_BALANCE,
            "code": b"",
        },
    ),
]

GenesisState = Iterable[Tuple[Address, Dict[str, Any]]]
