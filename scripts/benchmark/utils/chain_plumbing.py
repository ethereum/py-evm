from typing import (
    Any,
    Iterable,
    NamedTuple,
    Type
)

from eth_keys import (
    keys
)

from eth_utils import (
    decode_hex,
    to_dict,
    to_wei,
)

from eth_typing import (
    Address
)

from evm import (
    constants,
    Chain
)
from evm.vm.base import (
    BaseVM
)
from evm.chains.mainnet import (
    MainnetChain
)
from evm.db.backends.memory import (
    MemoryDB
)

AddressSetup = NamedTuple('AddressSetup', [
    ('address', Address),
    ('balance', int),
    ('code', bytes)
])

ALL_VM = [vm for _, vm in MainnetChain.vm_configuration]

FUNDED_ADDRESS_PRIVATE_KEY = keys.PrivateKey(
    decode_hex('0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8')
)

FUNDED_ADDRESS = Address(FUNDED_ADDRESS_PRIVATE_KEY.public_key.to_canonical_address())

DEFAULT_INITIAL_BALANCE = to_wei(1000, 'ether')

SECOND_EXISTING_ADDRESS = Address(b'\0' * 19 + b'\x02')

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


@to_dict
def genesis_state(setup: Iterable[AddressSetup]) -> Any:
    for value in setup:
        yield value.address, {
            "balance": value.balance,
            "nonce": 0,
            "code": value.code,
            "storage": {}
        }


def chain_without_pow(
        base_db: MemoryDB,
        vm: Type[BaseVM],
        genesis_params: Any,
        genesis_state: Any) -> Chain:

    vm_without_pow = vm.configure(validate_seal=lambda block: None)

    klass = Chain.configure(
        __name__='TestChain',
        vm_configuration=(
            (constants.GENESIS_BLOCK_NUMBER, vm_without_pow),
        ))
    chain = klass.from_genesis(base_db, genesis_params, genesis_state)
    return chain


def get_chain(vm: Type[BaseVM]) -> Chain:
    return chain_without_pow(
        MemoryDB(),
        vm,
        GENESIS_PARAMS,
        genesis_state([
            AddressSetup(
                address=FUNDED_ADDRESS,
                balance=DEFAULT_INITIAL_BALANCE,
                code=b''
            ),
            AddressSetup(
                address=SECOND_EXISTING_ADDRESS,
                balance=DEFAULT_INITIAL_BALANCE,
                code=b''
            )
        ])
    )


def get_all_chains() -> Iterable[Chain]:
    for vm in ALL_VM:
        chain = get_chain(vm)
        yield chain
