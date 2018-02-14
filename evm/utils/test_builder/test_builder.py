from collections import (
    defaultdict,
)
from functools import (
    partial,
)

from evm.db.state import (
    MainAccountStateDB,
)

from cytoolz import (
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
    normalize_environment,
    normalize_state,
    normalize_transaction,
    normalize_transaction_group,
    normalize_networks,
)
from .builder_utils import (
    add_transaction_to_group,
    calc_state_root,
    get_version_from_git,
    merge_nested,
    wrap_in_list,
)
from .formatters import (
    filled_formatter,
)


#
# Defaults
#

DEFAULT_ENVIRONMENT = {
    "currentCoinbase": to_canonical_address("0x2adc25665018aa1fe0e6bc666dac8fc2697ff9ba"),
    "currentDifficulty": 131072,
    "currentGasLimit": 1000000,
    "currentNumber": 1,
    "currentTimestamp": 1000,
    "previousHash": decode_hex(
        "0x5e20a0453cecd065ea59c37ac63e079ee08998b6045136a8ce6635c7912ec0b6"
    ),
}

DEFAULT_TRANSACTION = {
    "data": b"",
    "gasLimit": 100000,
    "gasPrice": 0,
    "nonce": 0,
    "secretKey": decode_hex("0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8"),
    "to": to_canonical_address("0x0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6"),
    "value": 0
}

ALL_NETWORKS = [
    "Frontier",
    "Homestead",
    "EIP150",
    "EIP158",
    "Byzantium"
]

ACCOUNT_STATE_DB_CLASSES = {
    "Frontier": MainAccountStateDB,
    "Homestead": MainAccountStateDB,
    "EIP150": MainAccountStateDB,
    "EIP158": MainAccountStateDB,
    "Byzantium": MainAccountStateDB,
}
assert all(network in ACCOUNT_STATE_DB_CLASSES for network in ALL_NETWORKS)

FILLED_WITH_TEMPLATE = "py-evm-{version}"


#
# Filler Generation
#

def setup_filler(name, environment=None):
    environment = merge(DEFAULT_ENVIRONMENT, normalize_environment(environment or {}))
    return {name: {
        "env": environment,
    }}


@curry
def pre_state(pre_state, filler):
    assert len(filler) == 1
    test_name = next(iter(filler.keys()))

    old_pre_state = filler[test_name].get("pre_state", {})
    pre_state = normalize_state(pre_state)
    defaults = {address: {
        "balance": 0,
        "nonce": 0,
        "code": b"",
        "storage": {},
    } for address in pre_state}
    new_pre_state = merge_nested(defaults, old_pre_state, pre_state)

    return assoc_in(filler, [test_name, "pre"], new_pre_state)


def _expect(networks, transaction, post_state, filler):
    assert len(filler) == 1
    test_name = next(iter(filler.keys()))
    test = filler[test_name]

    networks = normalize_networks(networks)
    transaction = normalize_transaction(transaction)

    pre_state = test.get("pre", {})
    post_state = normalize_state(post_state)
    defaults = {address: {
        "balance": 0,
        "nonce": 0,
        "code": b"",
        "storage": {},
    } for address in post_state}
    result = merge_nested(defaults, pre_state, normalize_state(post_state))

    if "transaction" not in test:
        transaction = merge(DEFAULT_TRANSACTION, transaction)
        transaction_group = apply_formatters_to_dict({
            "data": wrap_in_list,
            "gasLimit": wrap_in_list,
            "value": wrap_in_list,
        }, transaction)
        indexes = {
            "data": 0,
            "gas": 0,
            "value": 0,
        }
    else:
        transaction_group, indexes = add_transaction_to_group(
            test["transaction"], transaction
        )

    existing_expect = test.get("expect", [])
    expect = existing_expect + [{
        "indexes": indexes,
        "network": networks,
        "result": result,
    }]

    return merge_nested(
        filler,
        {
            test_name: {
                "expect": expect,
                "transaction": transaction_group
            }
        }
    )


def expect(networks, transaction, post_state):
    return partial(_expect, networks, transaction, post_state)


#
# Test Filling
#

def fill_test(filler, comment="", apply_formatter=True):
    assert len(filler) == 1
    test_name = next(iter(filler.keys()))
    test = filler[test_name]

    environment = normalize_environment(test["env"])
    pre_state = normalize_state(test["pre"])
    transaction_group = normalize_transaction_group(test["transaction"])

    info = {
        "filledwith": FILLED_WITH_TEMPLATE.format(version=get_version_from_git()),
        "comment": comment,
    }

    post = defaultdict(list)
    for expect in test["expect"]:
        indexes = expect["indexes"]
        networks = normalize_networks(expect["network"])
        result = normalize_state(expect["result"])
        post_state = merge_nested(pre_state, result)
        for network in networks:
            account_state_db_class = ACCOUNT_STATE_DB_CLASSES[network]
            post_state_root = calc_state_root(post_state, account_state_db_class)
            post[network].append({
                "hash": encode_hex(post_state_root),
                "indexes": indexes,
            })

    filled = {
        test_name: {
            "_info": info,
            "env": environment,
            "pre": pre_state,
            "transaction": transaction_group,
            "post": post
        }
    }
    if apply_formatter:
        return filled_formatter(filled)
    else:
        return filled
