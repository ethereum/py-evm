import functools

from typing import (
    Any,
    AnyStr,
    Callable,
    cast,
    Dict,
    Iterable,
    Mapping,
    Union,
)

from cytoolz import (
    assoc_in,
    compose,
    concat,
    identity,
)
import cytoolz.curried

from eth_typing import (
    Address,
)

from eth_utils import (
    apply_formatters_to_dict,
    big_endian_to_int,
    decode_hex,
    is_0x_prefixed,
    is_bytes,
    is_hex,
    is_integer,
    is_string,
    is_text,
    to_bytes,
    to_canonical_address,
    ValidationError,
)
import eth_utils.curried

from eth.constants import (
    CREATE_CONTRACT_ADDRESS,
)

from eth.tools._utils.mappings import (
    deep_merge,
    is_cleanly_mergable,
)

from eth.typing import (
    AccountState,
    GeneralState,
    IntConvertible,
    Normalizer,
    TransactionNormalizer,
)


#
# Primitives
#
@functools.lru_cache(maxsize=1024)
def normalize_int(value: IntConvertible) -> int:
    """
    Robust to integer conversion, handling hex values, string representations,
    and special cases like `0x`.
    """
    if is_integer(value):
        return cast(int, value)
    elif is_bytes(value):
        return big_endian_to_int(value)
    elif is_hex(value) and is_0x_prefixed(value):
        value = cast(str, value)
        if len(value) == 2:
            return 0
        else:
            return int(value, 16)
    elif is_string(value):
        return int(value)
    else:
        raise TypeError("Unsupported type: Got `{0}`".format(type(value)))


def normalize_bytes(value: Union[bytes, str]) -> bytes:
    if is_bytes(value):
        return cast(bytes, value)
    elif is_text(value) and is_hex(value):
        return decode_hex(value)
    elif is_text(value):
        return b''
    else:
        raise TypeError("Value must be either a string or bytes object")


@functools.lru_cache(maxsize=1024)
def to_int(value: str) -> int:
    """
    Robust to integer conversion, handling hex values, string representations,
    and special cases like `0x`.
    """
    if is_0x_prefixed(value):
        if len(value) == 2:
            return 0
        else:
            return int(value, 16)
    else:
        return int(value)


@functools.lru_cache(maxsize=128)
def normalize_to_address(value: AnyStr) -> Address:
    if value:
        return to_canonical_address(value)
    else:
        return CREATE_CONTRACT_ADDRESS


robust_decode_hex = eth_utils.curried.hexstr_if_str(to_bytes)


#
# Containers
#
def dict_normalizer(formatters: Dict[Any, Callable[..., Any]],
                    required: Iterable[Any]=None,
                    optional: Iterable[Any]=None) -> Normalizer:

    all_keys = set(formatters.keys())

    if required is None and optional is None:
        required_set_form = all_keys
    elif required is not None and optional is not None:
        raise ValueError("Both required and optional keys specified")
    elif required is not None:
        required_set_form = set(required)
    elif optional is not None:
        required_set_form = all_keys - set(optional)

    def normalizer(d: Dict[Any, Any]) -> Dict[str, Any]:
        keys = set(d.keys())
        missing_keys = required_set_form - keys
        superfluous_keys = keys - all_keys
        if missing_keys:
            raise KeyError("Missing required keys: {}".format(", ".join(missing_keys)))
        if superfluous_keys:
            raise KeyError("Superfluous keys: {}".format(", ".join(superfluous_keys)))

        return apply_formatters_to_dict(formatters, d)

    return normalizer


def dict_options_normalizer(normalizers: Iterable[Normalizer]) -> Normalizer:

    def normalize(d: Dict[Any, Any]) -> Dict[str, Any]:
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


#
# Composition
#
def state_definition_to_dict(state_definition: GeneralState) -> AccountState:
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
            raise ValidationError("Some state item is defined multiple times")
        state_dict = deep_merge(*state_dicts)
    else:
        assert TypeError("State definition must either be a mapping or a sequence")

    seen_keys = set(concat(d.keys() for d in state_dict.values()))
    bad_keys = seen_keys - set(["balance", "nonce", "storage", "code"])
    if bad_keys:
        raise ValidationError(
            "State definition contains the following invalid account fields: {}".format(
                ", ".join(bad_keys)
            )
        )

    return state_dict


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


normalize_main_transaction = cast(Normalizer, dict_normalizer({
    "data": normalize_bytes,
    "gasLimit": normalize_int,
    "gasPrice": normalize_int,
    "nonce": normalize_int,
    "secretKey": normalize_bytes,
    "to": normalize_to_address,
    "value": normalize_int,
}))


normalize_transaction = cast(TransactionNormalizer, dict_options_normalizer([
    normalize_main_transaction,
]))


normalize_main_transaction_group = cast(Normalizer, dict_normalizer({
    "data": eth_utils.curried.apply_formatter_to_array(normalize_bytes),
    "gasLimit": eth_utils.curried.apply_formatter_to_array(normalize_int),
    "gasPrice": normalize_int,
    "nonce": normalize_int,
    "secretKey": normalize_bytes,
    "to": normalize_to_address,
    "value": eth_utils.curried.apply_formatter_to_array(normalize_int),
}))


normalize_transaction_group = cast(TransactionNormalizer, dict_options_normalizer([
    normalize_main_transaction_group,
]))


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


normalize_main_environment = dict_normalizer({
    "currentCoinbase": to_canonical_address,
    "previousHash": normalize_bytes,
    "currentNumber": normalize_int,
    "currentDifficulty": normalize_int,
    "currentGasLimit": normalize_int,
    "currentTimestamp": normalize_int,
}, optional=["previousHash"])


normalize_environment = dict_options_normalizer([
    normalize_main_environment,
])
