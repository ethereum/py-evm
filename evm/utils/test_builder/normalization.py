from collections.abc import (
    Iterable,
    Mapping,
)

from cytoolz import (
    assoc_in,
    compose,
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


def state_list_to_dict(state_list):
    """Convert state definitions in list form to the canonical dict form.

    Example of state list elements:

        - `(address, "balance", 1)`
        - `(address, "nonce", 2)`
        - `(address, "code", b"3")`
        - `(address, "storage", 4, 5)`

    For storage, the second to last entry specifies the slot and the last one the value.
    """
    d = {}
    for state_item in state_list:
        d = assoc_in(d, state_item[:-1], state_item[-1])
    return d


normalize_int = compose(
    int,
    eth_utils.curried.apply_formatter_if(is_bytes, big_endian_to_int),
    eth_utils.curried.apply_formatter_if(lambda v: is_hex(v) and is_0x_prefixed(v), decode_hex),
)


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
        state_list_to_dict
    ),
)

normalize_environment = eth_utils.curried.apply_formatters_to_dict({
    "currentCoinbase": to_canonical_address,
    "currentDifficulty": normalize_int,
    "currentGasLimit": normalize_int,
    "currentNumber": normalize_int,
    "currentTimestamp": normalize_int,
    "previousHash": normalize_bytes,
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


normalize_networks = identity  # TODO: allow for ranges
