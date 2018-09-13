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
from eth.db.atomic import (
    AtomicDB,
)

AddressSetup = NamedTuple('AddressSetup', [
    ('address', Address),
    ('balance', int),
    ('code', bytes)
])

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
        base_db: AtomicDB,
        vm: Type[BaseVM],
        genesis_params: Any,
        genesis_state: Any) -> MiningChain:

    vm_without_pow = vm.configure(validate_seal=lambda block: None)

    klass = MiningChain.configure(
        __name__='TestChain',
        vm_configuration=(
            (constants.GENESIS_BLOCK_NUMBER, vm_without_pow),
        ))
    chain = klass.from_genesis(base_db, genesis_params, genesis_state)
    return chain


def get_chain(vm: Type[BaseVM]) -> MiningChain:
    return chain_without_pow(
        AtomicDB(),
        vm,
        GENESIS_PARAMS,
        genesis_state([
            AddressSetup(
                address=FUNDED_ADDRESS,
                balance=DEFAULT_INITIAL_BALANCE,
                code=b''
            ),
            AddressSetup(
                address=SECOND_ADDRESS,
                balance=DEFAULT_INITIAL_BALANCE,
                code=b''
            ),
        ])
    )


def get_all_chains() -> Iterable[MiningChain]:
    for vm in ALL_VM:
        chain = get_chain(vm)
        yield chain
