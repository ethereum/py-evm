import pytest

from eth_keys import keys

from cytoolz import (
    merge,
    dissoc,
    assoc,
)

from evm.constants import (
    UINT_256_MAX,
    SECPK1_N,
    ZERO_HASH32,
    ENTRY_POINT,
)
from evm.vm.message import (
    ShardingMessage,
)
from evm.vm.forks.sharding import (
    ShardingVM,
)
from evm.vm.forks.sharding.transactions import (
    ShardingTransaction,
)

from evm.rlp.headers import (
    BlockHeader,
)

from evm.db import (
    get_db_backend,
)
from evm.db.chain import (
    BaseChainDB,
)
from evm.db.state import (
    ShardingAccountStateDB,
)

from eth_utils import (
    to_canonical_address,
    int_to_big_endian,
    big_endian_to_int
)
from evm.utils.padding import (
    pad32,
    zpad_left,
)
from evm.utils.address import (
    generate_CREATE2_contract_address,
)
from evm.utils.keccak import keccak

from evm.auxiliary.user_account_contract.transaction import (
    UserAccountTransaction,
    UnsignedUserAccountTransaction,
)
from evm.auxiliary.user_account_contract.contract import (
    generate_account_bytecode,
    NONCE_GETTER_ID,
    ECRECOVER_ADDRESS as ECRECOVER_ADDRESS_INT,
)


PRIVATE_KEY = keys.PrivateKey(b"\x33" * 32)

ACCOUNT_CODE = generate_account_bytecode(PRIVATE_KEY.public_key.to_canonical_address())
ACCOUNT_ADDRESS = generate_CREATE2_contract_address(b"", ACCOUNT_CODE)
INITIAL_BALANCE = 10000000000

# contract that does nothing
NOOP_CONTRACT_CODE = b""
NOOP_CONTRACT_ADDRESS = generate_CREATE2_contract_address(b"", NOOP_CONTRACT_CODE)

# contract that reverts without returning data
FAILING_CONTRACT_CODE = b"\x61\x00\x00\xfd"  # PUSH2 0 0 REVERT
FAILING_CONTRACT_ADDRESS = generate_CREATE2_contract_address(b"", FAILING_CONTRACT_CODE)

# contract that logs available gas
# GAS PUSH1 0 MSTORE PUSH1 32 PUSH1 0 LOG0
GAS_LOGGING_CONTRACT_CODE = b"\x5a\x60\x00\x52\x60\x20\x60\x00\xa0"
GAS_LOGGING_CONTRACT_ADDRESS = generate_CREATE2_contract_address(b"", GAS_LOGGING_CONTRACT_CODE)

# contract that logs hash of passed data
# CALLDATASIZE PUSH1 0 PUSH1 0 CALLDATACOPY CALLDATASIZE PUSH1 0 SHA3 PUSH1 0 MSTORE PUSH1 32
# PUSH1 0 LOG0
DATA_LOGGING_CONTRACT_CODE = (
    b"\x36\x60\x00\x60\x00\x37\x36\x60\x00\x20\x60\x00\x52\x60\x20\x60\x00\xa0"
)
DATA_LOGGING_CONTRACT_ADDRESS = generate_CREATE2_contract_address(b"", DATA_LOGGING_CONTRACT_CODE)

HELPER_CONTRACTS = {
    ACCOUNT_ADDRESS: ACCOUNT_CODE,
    NOOP_CONTRACT_ADDRESS: NOOP_CONTRACT_CODE,
    FAILING_CONTRACT_ADDRESS: FAILING_CONTRACT_CODE,
    GAS_LOGGING_CONTRACT_ADDRESS: GAS_LOGGING_CONTRACT_CODE,
    DATA_LOGGING_CONTRACT_ADDRESS: DATA_LOGGING_CONTRACT_CODE,
}


DESTINATION_ADDRESS = b"\xbb" * 20
ECRECOVER_ADDRESS = zpad_left(int_to_big_endian(ECRECOVER_ADDRESS_INT), 20)

DEFAULT_BASE_TX_PARAMS = {
    "chain_id": 1,
    "shard_id": 1,
    "to": ACCOUNT_ADDRESS,
    "gas": 500000,
    "gas_price": 0,
    "access_list": [
        [ACCOUNT_ADDRESS, b"\x00" * 32],
        [ECRECOVER_ADDRESS],
    ],
    "code": b"",
}

DEFAULT_TX_PARAMS = merge(
    dissoc(DEFAULT_BASE_TX_PARAMS, "code"),
    {
        "destination": DESTINATION_ADDRESS,
        "value": 0,
        "min_block": 0,
        "max_block": UINT_256_MAX,
        "nonce": 0,
        "msg_data": b"",
        "access_list": DEFAULT_BASE_TX_PARAMS["access_list"] + [
            [DESTINATION_ADDRESS],
        ],
    }
)

SIGNED_DEFAULT_TRANSACTION = UnsignedUserAccountTransaction(**merge(DEFAULT_TX_PARAMS, {
    "nonce": 0,
})).as_signed_transaction(PRIVATE_KEY)
DEFAULT_V = SIGNED_DEFAULT_TRANSACTION.v
DEFAULT_R = SIGNED_DEFAULT_TRANSACTION.r
DEFAULT_S = SIGNED_DEFAULT_TRANSACTION.s


@pytest.fixture
def vm():
    header = BlockHeader(
        coinbase=to_canonical_address("8888f1f195afa192cfee860698584c030f4c9db1"),
        difficulty=131072,
        block_number=10,
        gas_limit=3141592,
        timestamp=1422494849,
        parent_hash=ZERO_HASH32,
    )
    chaindb = BaseChainDB(get_db_backend(), account_state_class=ShardingAccountStateDB)
    vm = ShardingVM(header=header, chaindb=chaindb)
    vm_state = vm.state
    with vm_state.state_db() as statedb:
        for address, code in HELPER_CONTRACTS.items():
            statedb.set_code(address, code)
        statedb.set_balance(ACCOUNT_ADDRESS, INITIAL_BALANCE)
    # Update state_root manually
    vm.block.header.state_root = vm_state.state_root

    return vm


def get_nonce(vm):
    computation, _ = vm.apply_transaction(ShardingTransaction(**merge(DEFAULT_BASE_TX_PARAMS, {
        "data": int_to_big_endian(NONCE_GETTER_ID),
    })))
    return big_endian_to_int(computation.output)


def test_get_nonce(vm):
    computation, _ = vm.apply_transaction(ShardingTransaction(**merge(DEFAULT_BASE_TX_PARAMS, {
        "data": int_to_big_endian(NONCE_GETTER_ID),
    })))
    assert computation.output == pad32(b"\x00")

    computation, _ = vm.apply_transaction(SIGNED_DEFAULT_TRANSACTION)

    computation, _ = vm.apply_transaction(ShardingTransaction(**merge(DEFAULT_BASE_TX_PARAMS, {
        "data": int_to_big_endian(NONCE_GETTER_ID),
    })))
    assert computation.output == pad32(b"\x01")


def test_call_increments_nonce(vm):
    computation, _ = vm.apply_transaction(SIGNED_DEFAULT_TRANSACTION)
    assert computation.is_success
    assert get_nonce(vm) == 1

    transaction = UnsignedUserAccountTransaction(**merge(DEFAULT_TX_PARAMS, {
        "nonce": 1,
    })).as_signed_transaction(PRIVATE_KEY)
    computation, _ = vm.apply_transaction(transaction)
    assert computation.is_success
    assert get_nonce(vm) == 2


def test_call_checks_nonce(vm):
    computation, _ = vm.apply_transaction(SIGNED_DEFAULT_TRANSACTION)
    assert computation.is_success

    computation, _ = vm.apply_transaction(SIGNED_DEFAULT_TRANSACTION)
    assert computation.is_error

    transaction = UnsignedUserAccountTransaction(**merge(DEFAULT_TX_PARAMS, {
        "nonce": 2,
    })).as_signed_transaction(PRIVATE_KEY)
    computation, _ = vm.apply_transaction(transaction)
    assert computation.is_error


@pytest.mark.parametrize("min_block,max_block,valid", [
    (min_block, max_block, True) for min_block, max_block in [
        (0, UINT_256_MAX),
        (0, 10),
        (10, 10),
        (10, UINT_256_MAX)
    ]] + [
    (min_block, max_block, False) for min_block, max_block in [
        (0, 9),
        (5, 9),
        (11, 20),
        (11, UINT_256_MAX),
        (11, 9),
        (UINT_256_MAX, 0),
    ]]
)
def test_call_checks_block_range(vm, min_block, max_block, valid):
    assert vm.block.number == 10

    transaction = UnsignedUserAccountTransaction(**merge(DEFAULT_TX_PARAMS, {
        "nonce": get_nonce(vm),
        "min_block": min_block,
        "max_block": max_block,
    })).as_signed_transaction(PRIVATE_KEY)
    computation, _ = vm.apply_transaction(transaction)

    if valid:
        assert computation.is_success
    else:
        assert computation.is_error


def test_call_transfers_value(vm):
    vm_state = vm.state
    with vm_state.state_db() as state_db:
        balance_sender_before = state_db.get_balance(ACCOUNT_ADDRESS)
        balance_destination_before = state_db.get_balance(DESTINATION_ADDRESS)
    # Update state_root manually
    vm.block.header.state_root = vm_state.state_root

    transaction = UnsignedUserAccountTransaction(**merge(DEFAULT_TX_PARAMS, {
        "nonce": get_nonce(vm),
        "value": 10
    })).as_signed_transaction(PRIVATE_KEY)
    computation, _ = vm.apply_transaction(transaction)
    assert computation.is_success

    vm_state = vm.state
    with vm_state.state_db() as state_db:
        balance_sender_after = state_db.get_balance(ACCOUNT_ADDRESS)
        balance_destination_after = state_db.get_balance(DESTINATION_ADDRESS)
    # Update state_root manually
    vm.block.header.state_root = vm_state.state_root

    assert balance_sender_after == balance_sender_before - 10
    assert balance_destination_after == balance_destination_before + 10


@pytest.mark.parametrize("v,r,s", [
    (0, 0, 0),

    (DEFAULT_V + 1, DEFAULT_R, DEFAULT_S),
    (DEFAULT_V + 2, DEFAULT_R, DEFAULT_S),
    (DEFAULT_V - 1, DEFAULT_R, DEFAULT_S),
    (0, DEFAULT_R, DEFAULT_S),
    (1, DEFAULT_R, DEFAULT_S),

    (DEFAULT_V, DEFAULT_R + 1, DEFAULT_S),
    (DEFAULT_V, DEFAULT_R - 1, DEFAULT_S),
    (DEFAULT_V, 0, DEFAULT_S),

    (DEFAULT_V, DEFAULT_R, DEFAULT_S + 1),
    (DEFAULT_V, DEFAULT_R, DEFAULT_S - 1),
    (DEFAULT_V, DEFAULT_R, 0),

    (27 if DEFAULT_V == 28 else 28, DEFAULT_R, SECPK1_N - DEFAULT_S),
])
def test_call_checks_signature(vm, v, r, s):
    transaction = UserAccountTransaction(**merge(DEFAULT_TX_PARAMS, {"v": v, "r": r, "s": s}))
    message_params = {
        "gas": transaction.gas,
        "gas_price": transaction.gas_price,
        "to": transaction.to,
        "sig_hash": transaction.sig_hash,
        "sender": ENTRY_POINT,
        "value": 0,
        "code": ACCOUNT_CODE,
        "transaction_gas_limit": transaction.gas,
        "is_create": False,
        "access_list": transaction.prefix_list,
    }
    message = ShardingMessage(**assoc(message_params, "data", transaction.data))
    computation = vm.state.get_computation(message)
    computation = computation.apply_message()
    assert computation.is_error

    # error is due to bad signature, so with tx should pass with original one
    message = ShardingMessage(**assoc(message_params, "data", SIGNED_DEFAULT_TRANSACTION.data))
    computation = vm.state.get_computation(message)
    computation = computation.apply_message()
    assert computation.is_success


def test_call_uses_remaining_gas(vm):
    transaction = UnsignedUserAccountTransaction(**merge(DEFAULT_TX_PARAMS, {
        "nonce": get_nonce(vm),
        "destination": GAS_LOGGING_CONTRACT_ADDRESS,
        "gas": 1 * 1000 * 1000,
        "access_list": DEFAULT_TX_PARAMS["access_list"] + [[GAS_LOGGING_CONTRACT_ADDRESS]],
    })).as_signed_transaction(PRIVATE_KEY)
    computation, _ = vm.apply_transaction(transaction)
    assert computation.is_success

    logs = computation.get_log_entries()
    assert len(logs) == 1
    logged_gas = big_endian_to_int(logs[0][-1])
    assert logged_gas > 900 * 1000  # some gas will have been consumed earlier


@pytest.mark.parametrize("data,hash", [
    (data, keccak(data)) for data in [
        b"",
        b"\x112233"
        b"\x00" * 32,
        b"\xff" * 32,
        b"\xaa" * 50,
        b"\x55" * 64,
        b"\x22" * 500,
    ]
])
def test_call_uses_data(vm, data, hash):
    transaction = UnsignedUserAccountTransaction(**merge(DEFAULT_TX_PARAMS, {
        "nonce": get_nonce(vm),
        "destination": DATA_LOGGING_CONTRACT_ADDRESS,
        "msg_data": data,
        "access_list": DEFAULT_TX_PARAMS["access_list"] + [[DATA_LOGGING_CONTRACT_ADDRESS]],
    })).as_signed_transaction(PRIVATE_KEY)
    computation, _ = vm.apply_transaction(transaction)
    assert computation.is_success

    logs = computation.get_log_entries()
    assert len(logs) == 1
    logged_hash = logs[0][-1]
    assert logged_hash == hash


def test_no_call_if_not_enough_gas(vm):
    transaction = UnsignedUserAccountTransaction(**merge(DEFAULT_TX_PARAMS, {
        "nonce": get_nonce(vm),
        "destination": NOOP_CONTRACT_ADDRESS,
        "gas": 55000,
        "access_list": DEFAULT_TX_PARAMS["access_list"] + [[NOOP_CONTRACT_ADDRESS]],
    })).as_signed_transaction(PRIVATE_KEY)
    computation, _ = vm.apply_transaction(transaction)
    assert computation.is_error
    # a little remains, but not enough to make the call
    assert computation.gas_meter.gas_remaining > 0


def test_call_passes_return_code(vm):
    transaction = UnsignedUserAccountTransaction(**merge(DEFAULT_TX_PARAMS, {
        "nonce": get_nonce(vm),
        "destination": NOOP_CONTRACT_ADDRESS,
        "access_list": DEFAULT_TX_PARAMS["access_list"] + [[NOOP_CONTRACT_ADDRESS]],
    })).as_signed_transaction(PRIVATE_KEY)
    computation, _ = vm.apply_transaction(transaction)
    assert computation.is_success
    assert big_endian_to_int(computation.output) == 1  # success

    transaction = UnsignedUserAccountTransaction(**merge(DEFAULT_TX_PARAMS, {
        "nonce": get_nonce(vm),
        "destination": FAILING_CONTRACT_ADDRESS,
        "access_list": DEFAULT_TX_PARAMS["access_list"] + [[FAILING_CONTRACT_ADDRESS]],
    })).as_signed_transaction(PRIVATE_KEY)
    computation, _ = vm.apply_transaction(transaction)
    assert computation.is_success
    assert big_endian_to_int(computation.output) == 0  # failure


def test_call_does_not_revert_nonce(vm):
    nonce_before = get_nonce(vm)
    transaction = UnsignedUserAccountTransaction(**merge(DEFAULT_TX_PARAMS, {
        "nonce": nonce_before,
        "destination": FAILING_CONTRACT_ADDRESS,
        "access_list": DEFAULT_TX_PARAMS["access_list"] + [[FAILING_CONTRACT_ADDRESS]],
    })).as_signed_transaction(PRIVATE_KEY)
    computation, _ = vm.apply_transaction(transaction)
    assert computation.is_success
    assert get_nonce(vm) == nonce_before + 1


def test_nonce_getter_id():
    assert NONCE_GETTER_ID == big_endian_to_int(keccak(b"get_nonce()")[:4])
