from typing import (
    Iterable,
    Type
)

from eth_keys import (
    keys
)

from eth_utils import (
    decode_hex,
    to_wei,
)

from eth_typing import (
    Address
)

from eth import (
    constants,
)
from eth.chains.base import (
    MiningChain,
)
from eth.vm.base import (
    BaseVM
)
from eth.chains.mainnet import (
    BaseMainnetChain,
)
from eth.tools.builder.chain import (
    build,
    disable_pow_check,
    fork_at,
    genesis,
)

ALL_VM = [vm for _, vm in BaseMainnetChain.vm_configuration]

FUNDED_ADDRESS_PRIVATE_KEY = keys.PrivateKey(
    decode_hex('0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8')
)

FUNDED_ADDRESS = Address(FUNDED_ADDRESS_PRIVATE_KEY.public_key.to_canonical_address())

DEFAULT_INITIAL_BALANCE = to_wei(10000, 'ether')

SECOND_ADDRESS_PRIVATE_KEY = keys.PrivateKey(
    decode_hex('0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d0')
)

SECOND_ADDRESS = Address(SECOND_ADDRESS_PRIVATE_KEY.public_key.to_canonical_address())

GENESIS_PARAMS = {
    'parent_hash': constants.GENESIS_PARENT_HASH,
    'uncles_hash': constants.EMPTY_UNCLE_HASH,
    'coinbase': constants.ZERO_ADDRESS,
    'transaction_root': constants.BLANK_ROOT_HASH,
    'receipt_root': constants.BLANK_ROOT_HASH,
    'difficulty': 1,
    'block_number': constants.GENESIS_BLOCK_NUMBER,
    'gas_limit': constants.GENESIS_GAS_LIMIT,
    'extra_data': constants.GENESIS_EXTRA_DATA,
    'nonce': constants.GENESIS_NONCE
}


def get_chain(vm: Type[BaseVM]) -> MiningChain:
    # Genesis Block state
    gen_state = [
        (FUNDED_ADDRESS, {
            "balance": DEFAULT_INITIAL_BALANCE,
            "code": b'',
        }),
        (SECOND_ADDRESS, {
            "balance": DEFAULT_INITIAL_BALANCE,
            "code": b'',
        }),
    ]

    vm_without_pow = vm.configure(validate_seal=lambda block: None)

    chain = build(
        MiningChain,
        fork_at(vm_without_pow, constants.GENESIS_BLOCK_NUMBER),
        disable_pow_check(),
        genesis(params=GENESIS_PARAMS, state=gen_state)
    )

    return chain


def get_all_chains() -> Iterable[MiningChain]:
    for vm in ALL_VM:
        chain = get_chain(vm)
        yield chain
