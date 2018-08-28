from collections import defaultdict
from typing import (  # noqa: F401
    Dict,
    List,
)

from eth_utils import encode_hex

from eth.db.account import (
    AccountDB,
)
from eth.tools.fixtures.helpers import (
    get_test_name,
)
from eth.tools.fixtures.normalization import (
    normalize_environment,
    normalize_networks,
    normalize_state,
    normalize_transaction_group,
)
from eth.tools._utils.mappings import deep_merge

from ._utils import (
    calc_state_root,
)


ALL_NETWORKS = [
    "Frontier",
    "Homestead",
    "EIP150",
    "EIP158",
    "Byzantium",
    "Constantinople",
]

ACCOUNT_STATE_DB_CLASSES = {
    "Frontier": AccountDB,
    "Homestead": AccountDB,
    "EIP150": AccountDB,
    "EIP158": AccountDB,
    "Byzantium": AccountDB,
    "Constantinople": AccountDB,
}
assert all(network in ACCOUNT_STATE_DB_CLASSES for network in ALL_NETWORKS)


def fill_state_test(filler):
    """
    Filler function for filling state tests.
    """
    test_name = get_test_name(filler)
    test = filler[test_name]

    environment = normalize_environment(test["env"])
    pre_state = normalize_state(test["pre"])
    transaction_group = normalize_transaction_group(test["transaction"])

    post = defaultdict(list)  # type: Dict[int, List[Dict[str, str]]]
    for expect in test["expect"]:
        indexes = expect["indexes"]
        networks = normalize_networks(expect["networks"])
        result = normalize_state(expect["result"])
        post_state = deep_merge(pre_state, result)
        for network in networks:
            account_db_class = ACCOUNT_STATE_DB_CLASSES[network]
            post_state_root = calc_state_root(post_state, account_db_class)
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
