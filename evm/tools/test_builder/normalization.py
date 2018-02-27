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
    apply_formatters_to_dict,
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

from evm.constants import (
    CREATE_CONTRACT_ADDRESS,
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
        if not is_cleanly_mergable(*state_dicts):
            raise ValueError("Some state item is defined multiple times")
        state_dict = deep_merge(*state_dicts)
    else:
        assert TypeError("State definition must either be a mapping or a sequence")

    seen_keys = set(concat(d.keys() for d in state_dict.values()))
    bad_keys = seen_keys - set(["balance", "nonce", "storage", "code"])
    if bad_keys:
        raise ValueError(
            "State definition contains the following invalid account fields: {}".format(
                ", ".join(bad_keys)
            )
        )

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


def normalize_bytes(value):
    if is_hex(value) or len(value) == 0:
        return decode_hex(value)
    elif is_bytes(value):
        return value
    else:
        raise TypeError("Value must be either a string or bytes object")


@functools.lru_cache(maxsize=128)
def normalize_to_address(value):
    if value:
        return to_canonical_address(value)
    else:
        return CREATE_CONTRACT_ADDRESS


def dict_normalizer(formatters, required=None, optional=None):
    all_keys = set(formatters.keys())

    if required is None and optional is None:
        required = all_keys
    elif required is not None:
        required = set(required)
    elif optional is not None:
        required = all_keys - set(optional)
    else:
        raise ValueError("Both required and optional keys specified")

    def normalizer(d):
        keys = set(d.keys())
        missing_keys = required - keys
        superfluous_keys = keys - all_keys
        if missing_keys:
            raise KeyError("Missing required keys: {}".format(", ".join(missing_keys)))
        if superfluous_keys:
            raise KeyError("Superfluous keys: {}".format(", ".join(superfluous_keys)))

        return apply_formatters_to_dict(formatters, d)

    return normalizer


def dict_options_normalizer(normalizers):

    def normalize(d):
        first_exception = None
        for normalizer in normalizers:
            try:
                normalized = normalizer(d)
            except KeyError as e:
                if not first_exception:
                    first_exception = e
            else:
                return normalized
        assert first_exception is not None
        raise first_exception

    return normalize


normalize_storage = compose(
    cytoolz.curried.keymap(normalize_int),
    cytoolz.curried.valmap(normalize_int),
)


normalize_state = compose(
    cytoolz.curried.keymap(to_canonical_address),
    cytoolz.curried.valmap(dict_normalizer({
        "balance": normalize_int,
        "code": normalize_bytes,
        "nonce": normalize_int,
        "storage": normalize_storage
    }, required=[])),
    eth_utils.curried.apply_formatter_if(
        lambda s: isinstance(s, Iterable) and not isinstance(s, Mapping),
        state_definition_to_dict
    ),
)


normalize_main_environment = dict_normalizer({
    "currentCoinbase": to_canonical_address,
    "previousHash": normalize_bytes,
    "currentNumber": normalize_int,
    "currentDifficulty": normalize_int,
    "currentGasLimit": normalize_int,
    "currentTimestamp": normalize_int,
}, optional=["previousHash"])


normalize_sharding_environment = dict_normalizer({
    "currentCoinbase": to_canonical_address,
    "previousHash": normalize_bytes,
    "currentNumber": normalize_int,
    "shardID": normalize_int,
    "expectedPeriodNumber": normalize_int,
    "periodStartHash": normalize_bytes,
    "currentCoinbase": to_canonical_address,
    "currentNumber": normalize_int,
})


normalize_environment = dict_options_normalizer([
    normalize_main_environment,
    normalize_sharding_environment,
])


normalize_main_transaction = dict_normalizer({
    "data": normalize_bytes,
    "gasLimit": normalize_int,
    "gasPrice": normalize_int,
    "nonce": normalize_int,
    "secretKey": normalize_bytes,
    "to": normalize_to_address,
    "value": normalize_int,
})


normalize_access_list = eth_utils.curried.apply_formatter_to_array(
    eth_utils.curried.apply_formatter_to_array(normalize_bytes)
)

normalize_sharding_transaction = dict_normalizer({
    "chainID": normalize_int,
    "shardID": normalize_int,
    "data": normalize_bytes,
    "gasLimit": normalize_int,
    "gasPrice": normalize_int,
    "to": normalize_to_address,
    "code": normalize_bytes,
    "accessList": normalize_access_list,
})


normalize_transaction = dict_options_normalizer([
    normalize_main_transaction,
    normalize_sharding_transaction,
])


normalize_main_transaction_group = dict_normalizer({
    "data": eth_utils.curried.apply_formatter_to_array(normalize_bytes),
    "gasLimit": eth_utils.curried.apply_formatter_to_array(normalize_int),
    "gasPrice": normalize_int,
    "nonce": normalize_int,
    "secretKey": normalize_bytes,
    "to": normalize_to_address,
    "value": eth_utils.curried.apply_formatter_to_array(normalize_int),
})


normalize_sharding_transaction_group = dict_normalizer({
    "chainID": normalize_int,
    "shardID": normalize_int,
    "data": eth_utils.curried.apply_formatter_to_array(normalize_bytes),
    "gasLimit": eth_utils.curried.apply_formatter_to_array(normalize_int),
    "gasPrice": normalize_int,
    "to": normalize_to_address,
    "code": normalize_bytes,
    "accessList": normalize_access_list,
})


normalize_transaction_group = dict_options_normalizer([
    normalize_main_transaction_group,
    normalize_sharding_transaction_group,
])


normalize_execution = dict_normalizer({
    "address": to_canonical_address,
    "origin": to_canonical_address,
    "caller": to_canonical_address,
    "value": normalize_int,
    "data": normalize_bytes,
    "gasPrice": normalize_int,
    "gas": normalize_int,
})


normalize_networks = identity


normalize_call_create_item = dict_normalizer({
    "data": normalize_bytes,
    "destination": to_canonical_address,
    "gasLimit": normalize_int,
    "value": normalize_int,
})
normalize_call_creates = eth_utils.curried.apply_formatter_to_array(normalize_call_create_item)

normalize_log_item = dict_normalizer({
    "address": to_canonical_address,
    "topics": eth_utils.curried.apply_formatter_to_array(normalize_int),
    "data": normalize_bytes,
})
normalize_logs = eth_utils.curried.apply_formatter_to_array(normalize_log_item)
