from collections.abc import (
    Iterable,
    Mapping,
)
import functools

from cytoolz import (
    assoc_in,
    compose,
    concat,
    identity,
)
from eth_utils import (
    big_endian_to_int,
    decode_hex,
    is_0x_prefixed,
    is_bytes,
    is_hex,
    to_canonical_address,
)
import cytoolz.curried
import eth_utils.curried

from .builder_utils import (
    deep_merge,
    is_cleanly_mergable,
)


def state_definition_to_dict(state_definition):
    """Convert a state definition to the canonical dict form.

    State can either be defined in the canonical form, or as a list of sub states that are then
    merged to one. Sub states can either be given as dictionaries themselves, or as tuples where
    the last element is the value and all others the keys for this value in the nested state
    dictionary. Example:

    ```
        [
            ("0xaabb", "balance", 3),
            ("0xaabb", "storage", {
                4: 5,
            }),
            "0xbbcc", {
                "balance": 6,
                "nonce": 7
            }
        ]
    ```
    """
    if isinstance(state_definition, Mapping):
        state_dict = state_definition
    elif isinstance(state_definition, Iterable):
        state_dicts = [
            assoc_in(
                {},
                state_item[:-1],
                state_item[-1]
            ) if not isinstance(state_item, Mapping) else state_item
            for state_item
            in state_definition
        ]
        assert is_cleanly_mergable(*state_dicts)
        state_dict = deep_merge(*state_dicts)
    else:
        assert False

    second_layer_keys = concat(d.keys() for d in state_dict.values())
    assert all(key in ["balance", "nonce", "storage", "code"] for key in second_layer_keys)

    return state_dict


@functools.lru_cache(maxsize=1024)
def normalize_int(value):
    """
    Robust to integer conversion, handling hex values, string representations,
    and special cases like `0x`.
    """
    if is_bytes(value):
        return big_endian_to_int(value)
    if is_hex(value) and is_0x_prefixed(value):
        if len(value) == 2:
            return 0
        else:
            return int(value, 16)
    else:
        return int(value)


normalize_bytes = eth_utils.curried.apply_formatter_if(is_hex, decode_hex)


normalize_storage = compose(
    cytoolz.curried.keymap(normalize_int),
    cytoolz.curried.valmap(normalize_int),
)


normalize_state = compose(
    cytoolz.curried.keymap(to_canonical_address),
    cytoolz.curried.valmap(eth_utils.curried.apply_formatters_to_dict({
        "balance": normalize_int,
        "code": normalize_bytes,
        "nonce": normalize_int,
        "storage": normalize_storage
    })),
    eth_utils.curried.apply_formatter_if(
        lambda s: isinstance(s, Iterable) and not isinstance(s, Mapping),
        state_definition_to_dict
    ),
)


normalize_environment = eth_utils.curried.apply_formatters_to_dict({
    # shared
    "currentCoinbase": to_canonical_address,
    "previousHash": normalize_bytes,
    "currentNumber": normalize_int,

    # only main environment
    "currentDifficulty": normalize_int,
    "currentGasLimit": normalize_int,
    "currentTimestamp": normalize_int,

    # only sharding environment
    "shardID": normalize_int,
    "expectedPeriodNumber": normalize_int,
    "periodStartHash": normalize_bytes,
    "currentCoinbase": to_canonical_address,
    "currentNumber": normalize_int,
})


normalize_transaction = eth_utils.curried.apply_formatters_to_dict({
    "data": normalize_bytes,
    "gasLimit": normalize_int,
    "gasPrice": normalize_int,
    "nonce": normalize_int,
    "secretKey": normalize_bytes,
    "to": to_canonical_address,
    "value": normalize_int,
})


normalize_transaction_group = eth_utils.curried.apply_formatters_to_dict({
    "data": eth_utils.curried.apply_formatter_to_array(normalize_bytes),
    "gasLimit": eth_utils.curried.apply_formatter_to_array(normalize_int),
    "gasPrice": normalize_int,
    "nonce": normalize_int,
    "secretKey": normalize_bytes,
    "to": to_canonical_address,
    "value": eth_utils.curried.apply_formatter_to_array(normalize_int),
})


normalize_execution = eth_utils.curried.apply_formatters_to_dict({
    "address": to_canonical_address,
    "origin": to_canonical_address,
    "caller": to_canonical_address,
    "value": normalize_int,
    "data": normalize_bytes,
    "gasPrice": normalize_int,
    "gas": normalize_int,
})


normalize_networks = identity  # TODO: allow for ranges


normalize_call_create_item = eth_utils.curried.apply_formatters_to_dict({
    "data": normalize_bytes,
    "destination": to_canonical_address,
    "gasLimit": normalize_int,
    "value": normalize_int,
})
normalize_call_creates = eth_utils.curried.apply_formatter_to_array(normalize_call_create_item)

normalize_log_item = eth_utils.curried.apply_formatters_to_dict({
    "address": to_canonical_address,
    "topics": eth_utils.curried.apply_formatter_to_array(normalize_int),
    "data": normalize_bytes,
})
normalize_logs = eth_utils.curried.apply_formatter_to_array(normalize_log_item)
