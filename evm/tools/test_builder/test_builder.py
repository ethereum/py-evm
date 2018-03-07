from collections import (
    defaultdict,
    namedtuple,
)
from functools import (
    partial,
)

from evm.db.state import (
    MainAccountStateDB,
    ShardingAccountStateDB,
)
from evm.tools.fixture_tests import (
    hash_log_entries,
)

from cytoolz import (
    assoc,
    assoc_in,
    curry,
    merge,
)
from eth_utils import (
    apply_formatters_to_dict,
    decode_hex,
    encode_hex,
    to_canonical_address,
)

from .normalization import (
    normalize_bytes,
    normalize_call_creates,
    normalize_environment,
    normalize_execution,
    normalize_int,
    normalize_logs,
    normalize_state,
    normalize_transaction,
    normalize_transaction_group,
    normalize_networks,
)
from .builder_utils import (
    add_transaction_to_group,
    calc_state_root,
    compile_vyper_lll,
    get_test_name,
    get_version_from_git,
    deep_merge,
    wrap_in_list,
)
from .formatters import (
    filled_state_test_formatter,
    filled_vm_test_formatter,
)


#
# Defaults
#

DEFAULT_MAIN_ENVIRONMENT = {
    "currentCoinbase": to_canonical_address("0x2adc25665018aa1fe0e6bc666dac8fc2697ff9ba"),
    "currentDifficulty": 131072,
    "currentGasLimit": 1000000,
    "currentNumber": 1,
    "currentTimestamp": 1000,
    "previousHash": decode_hex(
        "0x5e20a0453cecd065ea59c37ac63e079ee08998b6045136a8ce6635c7912ec0b6"
    ),
}

DEFAULT_SHARDING_ENVIRONMENT = {
    "shardID": 0,
    "expectedPeriodNumber": 0,
    "periodStartHash": decode_hex(
        "0x148067ef259ce711201e6b2a8438b907d0ac0549deef577aff58f1b9143a134a"
    ),
    "currentCoinbase": to_canonical_address("0x2adc25665018aa1fe0e6bc666dac8fc2697ff9ba"),
    "currentNumber": 1,
    "previousHash": decode_hex(
        "0x5e20a0453cecd065ea59c37ac63e079ee08998b6045136a8ce6635c7912ec0b6"
    ),
}


DEFAULT_MAIN_TRANSACTION = {
    "data": b"",
    "gasLimit": 100000,
    "gasPrice": 0,
    "nonce": 0,
    "secretKey": decode_hex("0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8"),
    "to": to_canonical_address("0x0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6"),
    "value": 0
}

DEFAULT_SHARDING_TRANSACTION = {
    "chainID": 0,
    "shardID": 0,
    "to": to_canonical_address("0x0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6"),
    "data": b"",
    "gasLimit": 100000,
    "gasPrice": 0,
    "accessList": [],
    "code": b"",
}


def get_default_transaction(networks):
    if "Sharding" not in networks:
        return DEFAULT_MAIN_TRANSACTION
    else:
        return DEFAULT_SHARDING_TRANSACTION


DEFAULT_EXECUTION = {
    "address": to_canonical_address("0x0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6"),
    "origin": to_canonical_address("0xcd1722f2947def4cf144679da39c4c32bdc35681"),
    "caller": to_canonical_address("0xcd1722f2947def4cf144679da39c4c32bdc35681"),
    "value": 1000000000000000000,
    "data": b"",
    "gasPrice": 1,
    "gas": 100000
}

ALL_NETWORKS = [
    "Frontier",
    "Homestead",
    "EIP150",
    "EIP158",
    "Byzantium",
    "Sharding",
]

ACCOUNT_STATE_DB_CLASSES = {
    "Frontier": MainAccountStateDB,
    "Homestead": MainAccountStateDB,
    "EIP150": MainAccountStateDB,
    "EIP158": MainAccountStateDB,
    "Byzantium": MainAccountStateDB,
    "Sharding": ShardingAccountStateDB,
}
assert all(network in ACCOUNT_STATE_DB_CLASSES for network in ALL_NETWORKS)

FILLED_WITH_TEMPLATE = "py-evm-{version}"


Test = namedtuple("Test", ["filler", "fill_kwargs"])
Test.__new__.__defaults__ = (None,)  # make `None` default for fill_kwargs


#
# Filler Generation
#

def setup_filler(name, environment=None):
    environment = normalize_environment(environment or {})
    return {name: {
        "env": environment,
        "pre": {},
    }}


def setup_main_filler(name, environment=None):
    return setup_filler(name, merge(DEFAULT_MAIN_ENVIRONMENT, environment or {}))


def setup_sharding_filler(name, environment=None):
    return setup_filler(name, merge(DEFAULT_SHARDING_ENVIRONMENT, environment or {}))


@curry
def pre_state(pre_state, filler):
    test_name = get_test_name(filler)

    old_pre_state = filler[test_name].get("pre_state", {})
    pre_state = normalize_state(pre_state)
    defaults = {address: {
        "balance": 0,
        "nonce": 0,
        "code": b"",
        "storage": {},
    } for address in pre_state}
    new_pre_state = deep_merge(defaults, old_pre_state, pre_state)

    return assoc_in(filler, [test_name, "pre"], new_pre_state)


def _expect(post_state, networks, transaction, filler):
    test_name = get_test_name(filler)
    test = filler[test_name]
    test_update = {test_name: {}}

    pre_state = test.get("pre", {})
    post_state = normalize_state(post_state or {})
    defaults = {address: {
        "balance": 0,
        "nonce": 0,
        "code": b"",
        "storage": {},
    } for address in post_state}
    result = deep_merge(defaults, pre_state, normalize_state(post_state))
    new_expect = {"result": result}

    if transaction is not None:
        transaction = normalize_transaction(
            merge(get_default_transaction(networks), transaction)
        )
        if "transaction" not in test:
            transaction_group = apply_formatters_to_dict({
                "data": wrap_in_list,
                "gasLimit": wrap_in_list,
                "value": wrap_in_list,
            }, transaction)
            indexes = {
                index_key: 0
                for transaction_key, index_key in [
                    ("gasLimit", "gas"),
                    ("value", "value"),
                    ("data", "data"),
                ]
                if transaction_key in transaction_group
            }
        else:
            transaction_group, indexes = add_transaction_to_group(
                test["transaction"], transaction
            )
        new_expect = assoc(new_expect, "indexes", indexes)
        test_update = assoc_in(test_update, [test_name, "transaction"], transaction_group)

    if networks is not None:
        networks = normalize_networks(networks)
        new_expect = assoc(new_expect, "networks", networks)

    existing_expects = test.get("expect", [])
    expect = existing_expects + [new_expect]
    test_update = assoc_in(test_update, [test_name, "expect"], expect)

    return deep_merge(filler, test_update)


def expect(post_state=None, networks=None, transaction=None):
    return partial(_expect, post_state, networks, transaction)


@curry
def execution(execution, filler):
    execution = normalize_execution(execution or {})

    # user caller as origin if not explicitly given
    if "caller" in execution and "origin" not in execution:
        execution = assoc(execution, "origin", execution["caller"])

    if "vyperLLLCode" in execution:
        code = compile_vyper_lll(execution["vyperLLLCode"])
        if "code" in execution:
            if code != execution["code"]:
                raise ValueError("Compiled Vyper LLL code does not match")
        execution = assoc(execution, "code", code)

    execution = merge(DEFAULT_EXECUTION, execution)

    test_name = get_test_name(filler)
    return deep_merge(
        filler,
        {
            test_name: {
                "exec": execution,
            }
        }
    )


#
# Test Filling
#

def fill_test(filler, info=None, apply_formatter=True, **kwargs):
    test_name = get_test_name(filler)
    test = filler[test_name]

    if "transaction" in test:
        filled = fill_state_test(filler, **kwargs)
        formatter = filled_state_test_formatter
    elif "exec" in test:
        filled = fill_vm_test(filler, **kwargs)
        formatter = filled_vm_test_formatter
    else:
        raise ValueError("Given filler does not appear to be for VM or state test")

    info = merge(
        {"filledwith": FILLED_WITH_TEMPLATE.format(version=get_version_from_git())},
        info if info else {}
    )
    filled = assoc_in(filled, [test_name, "_info"], info)

    if apply_formatter:
        return formatter(filled)
    else:
        return filled


def fill_state_test(filler):
    test_name = get_test_name(filler)
    test = filler[test_name]

    environment = normalize_environment(test["env"])
    pre_state = normalize_state(test["pre"])
    transaction_group = normalize_transaction_group(test["transaction"])

    post = defaultdict(list)
    for expect in test["expect"]:
        indexes = expect["indexes"]
        networks = normalize_networks(expect["networks"])
        result = normalize_state(expect["result"])
        post_state = deep_merge(pre_state, result)
        for network in networks:
            account_state_db_class = ACCOUNT_STATE_DB_CLASSES[network]
            post_state_root = calc_state_root(post_state, account_state_db_class)
            post[network].append({
                "hash": encode_hex(post_state_root),
                "indexes": indexes,
            })

    return {
        test_name: {
            "env": environment,
            "pre": pre_state,
            "transaction": transaction_group,
            "post": post
        }
    }


def fill_vm_test(
    filler,
    *,
    call_creates=None,
    gas_price=None,
    gas_remaining=0,
    logs=None,
    output=b""
):
    test_name = get_test_name(filler)
    test = filler[test_name]

    environment = normalize_environment(test["env"])
    pre_state = normalize_state(test["pre"])
    execution = normalize_execution(test["exec"])

    assert len(test["expect"]) == 1
    expect = test["expect"][0]
    assert "network" not in test
    assert "indexes" not in test

    result = normalize_state(expect["result"])
    post_state = deep_merge(pre_state, result)

    call_creates = normalize_call_creates(call_creates or [])
    gas_remaining = normalize_int(gas_remaining)
    output = normalize_bytes(output)

    logs = normalize_logs(logs or [])
    log_hash = hash_log_entries(logs)

    return {
        test_name: {
            "env": environment,
            "pre": pre_state,
            "exec": execution,
            "post": post_state,
            "callcreates": call_creates,
            "gas": gas_remaining,
            "output": output,
            "logs": log_hash,
        }
    }
