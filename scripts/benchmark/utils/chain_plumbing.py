import shutil
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
from eth.db.backends.base import (
    BaseDB
)
from eth.db.backends.level import (
    LevelDB
)
from eth.db.backends.memory import (
    MemoryDB
)
from .address import (
    FIRST_ACCOUNT,
    SECOND_ACCOUNT,
)

AddressSetup = NamedTuple('AddressSetup', [
    ('address', Address),
    ('balance', int),
    ('code', bytes),
])

ALL_VM = [vm for _, vm in BaseMainnetChain.vm_configuration]

DEFAULT_INITIAL_BALANCE = to_wei(10000, 'ether')

GENESIS_PARAMS = {
    'parent_hash': constants.GENESIS_PARENT_HASH,
    'uncles_hash': constants.EMPTY_UNCLE_HASH,
    'coinbase': constants.ZERO_ADDRESS,
    'transaction_root': constants.BLANK_ROOT_HASH,
    'receipt_root': constants.BLANK_ROOT_HASH,
    'difficulty': 100,
    'block_number': constants.GENESIS_BLOCK_NUMBER,
    'gas_limit': constants.GENESIS_GAS_LIMIT,
    'extra_data': constants.GENESIS_EXTRA_DATA,
    'nonce': constants.GENESIS_NONCE,
    'timestamp': 0
}


class DB(NamedTuple):
    type: BaseDB
    args: Any

memory_db = DB(
    type=MemoryDB,
    args= None
)

level_db = DB(
    type=LevelDB,
    args="scripts/benchmark/db/benchmark.db"
)


@to_dict
def genesis_state(setup: Iterable[AddressSetup]) -> Any:
    for value in setup:
        yield value.address, {
            "balance": value.balance,
            "nonce": 0,
            "code": value.code,
            "storage": {}
        }


def chain(
        base_db: BaseDB,
        vm: Type[BaseVM],
        genesis_params: Any,
        genesis_state: Any,
        validate_POW: bool) -> MiningChain:

    if(validate_POW):
        _vm = vm.configure()
    else:
        _vm = vm.configure(validate_seal=lambda block: None)


    klass = MiningChain.configure(
        __name__='TestChain',
        vm_configuration=(
            (constants.GENESIS_BLOCK_NUMBER, _vm),
        ))
    chain = klass.from_genesis(base_db, genesis_params, genesis_state)
    return chain


def get_chain(db: DB, validate_POW: bool, vm: Type[BaseVM]) -> MiningChain:
    return chain(
        db.type(db.args),
        vm,
        GENESIS_PARAMS,
        genesis_state([
            AddressSetup(
                address=FIRST_ACCOUNT.address,
                balance=DEFAULT_INITIAL_BALANCE,
                code=b''
            ),
            AddressSetup(
                address=SECOND_ACCOUNT.address,
                balance=DEFAULT_INITIAL_BALANCE,
                code=b''
            ),
        ]),
        validate_POW,
    )


def get_all_chains(db: DB, validate_POW: bool=True) -> Iterable[MiningChain]:
    for vm in ALL_VM:
        chain = get_chain(db, validate_POW, vm)
        yield chain

        if db.type == LevelDB:
            chain.chaindb.db.close()
            shutil.rmtree(db.args)
