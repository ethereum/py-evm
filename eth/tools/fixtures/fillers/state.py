from collections import (
    defaultdict,
)
from typing import (
    Any,
    Dict,
    List,
)

from eth_utils import (
    encode_hex,
)

from eth.tools._utils.mappings import (
    deep_merge,
)
from eth.tools._utils.normalization import (
    normalize_environment,
    normalize_networks,
    normalize_state,
    normalize_transaction_group,
)
from eth.tools.fixtures.helpers import (
    get_test_name,
)
from eth.vm.forks.byzantium.state import (
    ByzantiumState,
)
from eth.vm.forks.constantinople.state import (
    ConstantinopleState,
)
from eth.vm.forks.frontier.state import (
    FrontierState,
)
from eth.vm.forks.homestead.state import (
    HomesteadState,
)
from eth.vm.forks.istanbul.state import (
    IstanbulState,
)
from eth.vm.forks.petersburg.state import (
    PetersburgState,
)
from eth.vm.forks.spurious_dragon.state import (
    SpuriousDragonState,
)
from eth.vm.forks.tangerine_whistle.state import (
    TangerineWhistleState,
)

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
    "Petersburg",
    "Istanbul",
]

STATE_CLASSES = {
    "Frontier": FrontierState,
    "Homestead": HomesteadState,
    "EIP150": TangerineWhistleState,
    "EIP158": SpuriousDragonState,
    "Byzantium": ByzantiumState,
    "Constantinople": ConstantinopleState,
    "Petersburg": PetersburgState,
    "Istanbul": IstanbulState,
}

_missing_state_classes = set(ALL_NETWORKS) - set(STATE_CLASSES)
assert not any(_missing_state_classes)


def fill_state_test(filler: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Filler function for filling state tests.
    """
    test_name = get_test_name(filler)
    test = filler[test_name]

    environment = normalize_environment(test["env"])
    pre_state = normalize_state(test["pre"])
    transaction_group = normalize_transaction_group(test["transaction"])

    post: Dict[int, List[Dict[str, str]]] = defaultdict(list)
    for expect in test["expect"]:
        indexes = expect["indexes"]
        networks = normalize_networks(expect["networks"])
        result = normalize_state(expect["result"])
        post_state = deep_merge(pre_state, result)
        for network in networks:
            state_class = STATE_CLASSES[network]
            post_state_root = calc_state_root(post_state, state_class)
            post[network].append(
                {
                    "hash": encode_hex(post_state_root),
                    "indexes": indexes,
                }
            )

    return {
        test_name: {
            "env": environment,
            "pre": pre_state,
            "transaction": transaction_group,
            "post": post,
        }
    }
