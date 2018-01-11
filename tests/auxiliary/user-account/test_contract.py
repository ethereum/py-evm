import pytest

from eth_keys import keys

from evm.constants import (
    UINT_256_MAX,
    SECPK1_N,
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
    FlatTrieBackend,
    NestedTrieBackend,
)

from eth_utils import (
    to_canonical_address,
    decode_hex,
    int_to_big_endian,
    big_endian_to_int
)
from evm.utils.padding import pad32
from evm.utils.address import (
    generate_create2_contract_address,
)
from evm.utils.keccak import keccak

from evm.auxiliary.user_account_contract.transaction import (
    ForwardingTransaction,
)
from evm.auxiliary.user_account_contract.contract import (
    generate_validation_bytecode,
    generate_account_bytecode,
    NONCE_GETTER_ID,
    VALIDATION_CODE_GETTER_ID,
)


PRIVATE_KEY = keys.PrivateKey(b"\x33" * 32)

VALIDATION_CODE = generate_validation_bytecode(PRIVATE_KEY.public_key.to_canonical_address())
VALIDATION_CODE_ADDRESS = generate_create2_contract_address(b"", VALIDATION_CODE)

ACCOUNT_CODE = generate_account_bytecode(VALIDATION_CODE_ADDRESS)
ACCOUNT_ADDRESS = generate_create2_contract_address(b"", ACCOUNT_CODE)
INITIAL_BALANCE = 10000000000

# contract that does nothing
NOOP_CONTRACT_CODE = b""
NOOP_CONTRACT_ADDRESS = generate_create2_contract_address(b"", NOOP_CONTRACT_CODE)

# contract that reverts without returning data
FAILING_CONTRACT_CODE = b"\x61\x00\x00\xfd"  # PUSH2 0 0 REVERT
FAILING_CONTRACT_ADDRESS = generate_create2_contract_address(b"", FAILING_CONTRACT_CODE)

# contract that logs available gas
# GAS PUSH1 0 MSTORE PUSH1 32 PUSH1 0 LOG0
GAS_LOGGING_CONTRACT_CODE = b"\x5a\x60\x00\x52\x60\x20\x60\x00\xa0"
GAS_LOGGING_CONTRACT_ADDRESS = generate_create2_contract_address(b"", GAS_LOGGING_CONTRACT_CODE)

# contract that logs hash of passed data
# CALLDATASIZE PUSH1 0 PUSH1 0 CALLDATACOPY CALLDATASIZE PUSH1 0 SHA3 PUSH1 0 MSTORE PUSH1 32
# PUSH1 0 LOG0
DATA_LOGGING_CONTRACT_CODE = (
    b"\x36\x60\x00\x60\x00\x37\x36\x60\x00\x20\x60\x00\x52\x60\x20\x60\x00\xa0"
)
DATA_LOGGING_CONTRACT_ADDRESS = generate_create2_contract_address(b"", DATA_LOGGING_CONTRACT_CODE)

HELPER_CONTRACTS = {
    VALIDATION_CODE_ADDRESS: VALIDATION_CODE,
    ACCOUNT_ADDRESS: ACCOUNT_CODE,
    NOOP_CONTRACT_ADDRESS: NOOP_CONTRACT_CODE,
    FAILING_CONTRACT_ADDRESS: FAILING_CONTRACT_CODE,
    GAS_LOGGING_CONTRACT_ADDRESS: GAS_LOGGING_CONTRACT_CODE,
    DATA_LOGGING_CONTRACT_ADDRESS: DATA_LOGGING_CONTRACT_CODE,
}


DESTINATION_ADDRESS = b"\xbb" * 20

DEFAULT_BASE_TX_PARAMS = {
    "chain_id": 1,
    "shard_id": 1,
    "to": ACCOUNT_ADDRESS,
    "gas": 500000,
    "gas_price": 0,
    "access_list": [],
    "code": b"",
}

DEFAULT_TX_PARAMS = {**DEFAULT_BASE_TX_PARAMS, **{
    "destination": DESTINATION_ADDRESS,
    "value": 0,
    "min_block": 0,
    "max_block": UINT_256_MAX,
    "nonce": 0,
    "msg_data": b"",
}}
del DEFAULT_TX_PARAMS["code"]


@pytest.fixture
def chaindb():
    return BaseChainDB(get_db_backend(), state_backend_class=FlatTrieBackend)


def get_nonce(vm):
    computation = vm.apply_transaction(ShardingTransaction(**{**DEFAULT_BASE_TX_PARAMS, **{
        "data": pad32(int_to_big_endian(NONCE_GETTER_ID)),
    }}))
    return big_endian_to_int(computation.output)


def test_get_nonce(vm):
    computation = vm.apply_transaction(ShardingTransaction(**{**DEFAULT_BASE_TX_PARAMS, **{
        "data": pad32(int_to_big_endian(NONCE_GETTER_ID)),
    }}))
    assert computation.output == pad32(b"\x00")

    transaction = ForwardingTransaction(**{**DEFAULT_TX_PARAMS, **{
        "nonce": 0,
    }}).sign(PRIVATE_KEY)
    computation = vm.apply_transaction(transaction)

    computation = vm.apply_transaction(ShardingTransaction(**{**DEFAULT_BASE_TX_PARAMS, **{
        "data": pad32(int_to_big_endian(NONCE_GETTER_ID)),
    }}))
    assert computation.output == pad32(b"\x01")


def test_get_validation_code(vm):
    computation = vm.apply_transaction(ShardingTransaction(**{**DEFAULT_BASE_TX_PARAMS, **{
        "data": pad32(int_to_big_endian(VALIDATION_CODE_GETTER_ID)),
    }}))
    assert computation.output == VALIDATION_CODE_ADDRESS


@pytest.fixture
def vm():
    header = BlockHeader(
        coinbase=to_canonical_address("8888f1f195afa192cfee860698584c030f4c9db1"),
        difficulty=131072,
        block_number=10,
        gas_limit=3141592,
        timestamp=1422494849,
        parent_hash=decode_hex("0000000000000000000000000000000000000000000000000000000000000000"),
    )
    chaindb = BaseChainDB(get_db_backend(), state_backend_class=NestedTrieBackend)
    vm = ShardingVM(header=header, chaindb=chaindb)
    with vm.state.state_db() as state:
        for address, code in HELPER_CONTRACTS.items():
            state.set_code(address, code)
        state.set_balance(ACCOUNT_ADDRESS, INITIAL_BALANCE)

    return vm


def test_call_increments_nonce(vm):
    transaction = ForwardingTransaction(**{**DEFAULT_TX_PARAMS, **{
        "nonce": 0,
    }}).sign(PRIVATE_KEY)
    computation = vm.apply_transaction(transaction)
    assert computation.is_success
    assert get_nonce(vm) == 1

    transaction = ForwardingTransaction(**{**DEFAULT_TX_PARAMS, **{
        "nonce": 1,
    }}).sign(PRIVATE_KEY)
    computation = vm.apply_transaction(transaction)
    assert computation.is_success
    assert get_nonce(vm) == 2


def test_call_checks_nonce(vm):
    transaction = ForwardingTransaction(**{**DEFAULT_TX_PARAMS, **{
        "nonce": 0,
    }}).sign(PRIVATE_KEY)
    computation = vm.apply_transaction(transaction)
    assert computation.is_success

    computation = vm.apply_transaction(transaction)
    assert computation.is_error

    transaction = ForwardingTransaction(**{**DEFAULT_TX_PARAMS, **{
        "nonce": 2,
    }}).sign(PRIVATE_KEY)
    computation = vm.apply_transaction(transaction)
    assert computation.is_error


def test_call_checks_block_range(vm):
    assert vm.block.number == 10

    invalid_block_ranges = [
        (0, 9),
        (5, 9),
        (11, 20),
        (11, UINT_256_MAX),
        (11, 9),
        (UINT_256_MAX, 0),
    ]
    for min_block, max_block in invalid_block_ranges:
        transaction = ForwardingTransaction(**{**DEFAULT_TX_PARAMS, **{
            "nonce": get_nonce(vm),
            "min_block": min_block,
            "max_block": max_block,
        }}).sign(PRIVATE_KEY)
        computation = vm.apply_transaction(transaction)
        assert computation.is_error

    valid_block_ranges = [
        (0, UINT_256_MAX),
        (0, 10),
        (10, 10),
        (10, UINT_256_MAX)
    ]
    for min_block, max_block in valid_block_ranges:
        transaction = ForwardingTransaction(**{**DEFAULT_TX_PARAMS, **{
            "nonce": get_nonce(vm),
            "min_block": min_block,
            "max_block": max_block,
        }}).sign(PRIVATE_KEY)
        computation = vm.apply_transaction(transaction)
        assert computation.is_success


def test_call_transfers_value(vm):
    with vm.state.state_db() as state_db:
        balance_sender_before = state_db.get_balance(ACCOUNT_ADDRESS)
        balance_destination_before = state_db.get_balance(DESTINATION_ADDRESS)

    transaction = ForwardingTransaction(**{**DEFAULT_TX_PARAMS, **{
        "nonce": get_nonce(vm),
        "value": 10
    }}).sign(PRIVATE_KEY)
    computation = vm.apply_transaction(transaction)
    assert computation.is_success

    with vm.state.state_db() as state_db:
        balance_sender_after = state_db.get_balance(ACCOUNT_ADDRESS)
        balance_destination_after = state_db.get_balance(DESTINATION_ADDRESS)

    assert balance_sender_after == balance_sender_before - 10
    assert balance_destination_after == balance_destination_before + 10


def test_call_checks_signature(vm):
    transaction = ForwardingTransaction(**{**DEFAULT_TX_PARAMS, **{
        "nonce": get_nonce(vm),
    }}).sign(PRIVATE_KEY)

    v, r, s = transaction.vrs
    invalid_vrs_triples = [
        (v + 1, r, s),
        (v - 1, r, s),
        (0, r, s),
        (1, r, s),

        (v, r + 1, s),
        (v, r - 1, s),
        (v, 0, s),

        (v, r, s + 1),
        (v, r, s - 1),
        (v, r, 0),

        (27 if v == 28 else 28, r, SECPK1_N - s)
    ]

    for invalid_vrs in invalid_vrs_triples:
        transaction.vrs = invalid_vrs
        assert transaction.is_signed

        computation = vm.apply_transaction(transaction)
        assert computation.is_error


def test_call_uses_remaining_gas(vm):
    transaction = ForwardingTransaction(**{**DEFAULT_TX_PARAMS, **{
        "nonce": get_nonce(vm),
        "destination": GAS_LOGGING_CONTRACT_ADDRESS,
        "gas": 1 * 1000 * 1000,
    }}).sign(PRIVATE_KEY)
    computation = vm.apply_transaction(transaction)
    assert computation.is_success

    logs = computation.get_log_entries()
    assert len(logs) == 1
    assert big_endian_to_int(logs[0][-1]) > 900 * 1000  # some gas will have been consumed earlier


def test_call_uses_data(vm):
    data_and_hashes = [
        (data, keccak(data)) for data in [
            b"",
            b"\x112233"
            b"\x00" * 32,
            b"\xff" * 32,
            b"\xaa" * 50,
            b"\x55" * 64,
            b"\x22" * 500,
        ]
    ]
    for data, hash in data_and_hashes:
        transaction = ForwardingTransaction(**{**DEFAULT_TX_PARAMS, **{
            "nonce": get_nonce(vm),
            "destination": DATA_LOGGING_CONTRACT_ADDRESS,
            "msg_data": data
        }}).sign(PRIVATE_KEY)
        computation = vm.apply_transaction(transaction)
        assert computation.is_success

        logs = computation.get_log_entries()
        assert len(logs) == 1
        logged_hash = logs[0][-1]
        assert logged_hash == hash


def test_no_call_if_not_enough_gas(vm):
    transaction = ForwardingTransaction(**{**DEFAULT_TX_PARAMS, **{
        "nonce": get_nonce(vm),
        "destination": NOOP_CONTRACT_ADDRESS,
        "gas": 55000
    }}).sign(PRIVATE_KEY)
    computation = vm.apply_transaction(transaction)
    assert computation.is_error
    # a little remains, but not enough to make the call
    assert computation.gas_meter.gas_remaining > 0


def test_call_passes_return_code(vm):
    transaction = ForwardingTransaction(**{**DEFAULT_TX_PARAMS, **{
        "nonce": get_nonce(vm),
        "destination": NOOP_CONTRACT_ADDRESS,
    }}).sign(PRIVATE_KEY)
    computation = vm.apply_transaction(transaction)
    assert computation.is_success
    assert big_endian_to_int(computation.output) == 1  # success

    transaction = ForwardingTransaction(**{**DEFAULT_TX_PARAMS, **{
        "nonce": get_nonce(vm),
        "destination": FAILING_CONTRACT_ADDRESS,
    }}).sign(PRIVATE_KEY)
    computation = vm.apply_transaction(transaction)
    assert computation.is_success
    assert big_endian_to_int(computation.output) == 0  # failure


def test_call_does_not_revert_nonce(vm):
    nonce_before = get_nonce(vm)
    transaction = ForwardingTransaction(**{**DEFAULT_TX_PARAMS, **{
        "nonce": nonce_before,
        "destination": FAILING_CONTRACT_ADDRESS,
    }}).sign(PRIVATE_KEY)
    computation = vm.apply_transaction(transaction)
    assert computation.is_success
    assert get_nonce(vm) == nonce_before + 1
