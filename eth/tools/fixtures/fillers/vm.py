from typing import (
    Any,
    Dict,
    Iterable,
    Optional,
    Tuple,
    Union,
)

from eth.tools._utils.hashing import (
    hash_log_entries,
)
from eth.tools._utils.mappings import (
    deep_merge,
)
from eth.tools._utils.normalization import (
    normalize_bytes,
    normalize_call_creates,
    normalize_environment,
    normalize_execution,
    normalize_int,
    normalize_logs,
    normalize_state,
)
from eth.tools.fixtures.helpers import (
    get_test_name,
)


def fill_vm_test(
    filler: Dict[str, Any],
    *,
    call_creates: Optional[Any] = None,
    gas_price: Optional[Union[int, str]] = None,
    gas_remaining: Union[int, str] = 0,
    logs: Optional[Iterable[Tuple[bytes, Tuple[int, ...], bytes]]] = None,
    output: bytes = b""
) -> Dict[str, Dict[str, Any]]:
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
