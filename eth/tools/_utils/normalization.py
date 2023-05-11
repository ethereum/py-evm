import binascii
import functools
from typing import (
    Any,
    AnyStr,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Sequence,
    Tuple,
    Union,
    cast,
)

from eth_typing import (
    Address,
    HexStr,
)
from eth_utils.curried import (
    ValidationError,
    apply_formatter_if,
    apply_formatter_to_array,
    apply_formatters_to_dict,
    big_endian_to_int,
    decode_hex,
    hexstr_if_str,
    is_0x_prefixed,
    is_bytes,
    is_hex,
    is_integer,
    is_string,
    is_text,
    to_bytes,
    to_canonical_address,
    to_dict,
)
from eth_utils.toolz import (
    assoc_in,
    compose,
    concat,
    curried,
    curry,
    identity,
    merge,
)
from mypy_extensions import (
    TypedDict,
)

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
    TransactionDict,
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
        return big_endian_to_int(cast(bytes, value))
    elif is_hex(value) and is_0x_prefixed(value):  # type: ignore
        # mypy doesn't recognize that is_hex() forces value to be a str
        value = cast(str, value)
        if len(value) == 2:
            return 0
        else:
            return int(value, 16)
    elif is_string(value):
        return int(value)
    else:
        raise TypeError(f"Unsupported type: Got `{type(value)}`")


def normalize_bytes(value: Union[bytes, str]) -> bytes:
    if is_bytes(value):
        return cast(bytes, value)
    elif is_text(value) and is_hex(value):
        return decode_hex(cast(str, value))
    elif is_text(value):
        return b""
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


robust_decode_hex = hexstr_if_str(to_bytes)


#
# Containers
#
def dict_normalizer(
    formatters: Dict[Any, Callable[..., Any]],
    required: Iterable[Any] = None,
    optional: Iterable[Any] = None,
) -> Normalizer:
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
            raise KeyError(f"Missing required keys: {', '.join(missing_keys)}")
        if superfluous_keys:
            raise KeyError(f"Superfluous keys: {', '.join(superfluous_keys)}")

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

    State can either be defined in the canonical form, or as a list of sub states that
    are then merged to one. Sub states can either be given as dictionaries themselves,
    or as tuples where the last element is the value and all others the keys for this
    value in the nested state dictionary. Example:

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
            assoc_in({}, state_item[:-1], state_item[-1])
            if not isinstance(state_item, Mapping)
            else state_item
            for state_item in state_definition
        ]
        if not is_cleanly_mergable(*state_dicts):
            raise ValidationError("Some state item is defined multiple times")
        state_dict = deep_merge(*state_dicts)
    else:
        assert TypeError("State definition must either be a mapping or a sequence")

    seen_keys = set(concat(d.keys() for d in state_dict.values()))
    bad_keys = seen_keys - {"balance", "nonce", "storage", "code"}
    if bad_keys:
        raise ValidationError(
            "State definition contains the following invalid "
            f"account fields: {', '.join(bad_keys)}"
        )

    return state_dict


normalize_storage = compose(
    curried.keymap(normalize_int),
    curried.valmap(normalize_int),
)


normalize_state = compose(
    curried.keymap(to_canonical_address),
    curried.valmap(
        dict_normalizer(
            {
                "balance": normalize_int,
                "code": normalize_bytes,
                "nonce": normalize_int,
                "storage": normalize_storage,
            },
            required=[],
        )
    ),
    apply_formatter_if(
        lambda s: isinstance(s, Iterable) and not isinstance(s, Mapping),
        state_definition_to_dict,
    ),
)


normalize_main_transaction = dict_normalizer(
    {
        "data": normalize_bytes,
        "gasLimit": normalize_int,
        "gasPrice": normalize_int,
        "nonce": normalize_int,
        "secretKey": normalize_bytes,
        "to": normalize_to_address,
        "value": normalize_int,
    }
)


normalize_transaction = cast(
    TransactionNormalizer,
    dict_options_normalizer(
        [
            normalize_main_transaction,
        ]
    ),
)


normalize_main_transaction_group = dict_normalizer(
    {
        "data": apply_formatter_to_array(normalize_bytes),
        "gasLimit": apply_formatter_to_array(normalize_int),
        "gasPrice": normalize_int,
        "nonce": normalize_int,
        "secretKey": normalize_bytes,
        "to": normalize_to_address,
        "value": apply_formatter_to_array(normalize_int),
    }
)


normalize_transaction_group = cast(
    TransactionNormalizer,
    dict_options_normalizer(
        [
            normalize_main_transaction_group,
        ]
    ),
)


normalize_execution = dict_normalizer(
    {
        "address": to_canonical_address,
        "origin": to_canonical_address,
        "caller": to_canonical_address,
        "value": normalize_int,
        "data": normalize_bytes,
        "gasPrice": normalize_int,
        "gas": normalize_int,
    }
)


normalize_networks = identity


normalize_call_create_item = dict_normalizer(
    {
        "data": normalize_bytes,
        "destination": to_canonical_address,
        "gasLimit": normalize_int,
        "value": normalize_int,
    }
)
normalize_call_creates: Callable[[Iterable[Any]], Iterable[Any]]
normalize_call_creates = apply_formatter_to_array(normalize_call_create_item)

normalize_log_item = dict_normalizer(
    {
        "address": to_canonical_address,
        "topics": apply_formatter_to_array(normalize_int),
        "data": normalize_bytes,
    }
)
normalize_logs: Callable[[Iterable[Any]], Iterable[Any]]
normalize_logs = apply_formatter_to_array(normalize_log_item)


normalize_main_environment = dict_normalizer(
    {
        "currentCoinbase": to_canonical_address,
        "previousHash": normalize_bytes,
        "currentNumber": normalize_int,
        "currentDifficulty": normalize_int,
        "currentGasLimit": normalize_int,
        "currentTimestamp": normalize_int,
    },
    optional=["previousHash"],
)


normalize_environment = dict_options_normalizer(
    [
        normalize_main_environment,
    ]
)


#
# Fixture Normalizers
#
def normalize_unsigned_transaction(
    transaction: TransactionDict, indexes: Dict[str, Any]
) -> TransactionDict:
    normalized = normalize_transaction_group(transaction)
    return merge(
        normalized,
        {
            # Dynamic key access not yet allowed with TypedDict
            # https://github.com/python/mypy/issues/5359
            transaction_key: normalized[transaction_key][indexes[index_key]]  # type: ignore  # noqa: E501
            for transaction_key, index_key in [
                ("gasLimit", "gas"),
                ("value", "value"),
                ("data", "data"),
            ]
            if index_key in indexes
        },
    )


FixtureAccountDetails = TypedDict(
    "FixtureAccountDetails",
    {
        "balance": HexStr,
        "nonce": HexStr,
        "code": HexStr,
        "storage": Dict[HexStr, HexStr],
    },
)
FixtureAccountState = Dict[Address, FixtureAccountDetails]


def normalize_account_state(account_state: FixtureAccountState) -> AccountState:
    return {
        to_canonical_address(address): {
            "balance": to_int(state["balance"]),
            "code": decode_hex(state["code"]),
            "nonce": to_int(state["nonce"]),
            "storage": {
                to_int(slot): big_endian_to_int(decode_hex(value))
                for slot, value in state["storage"].items()
            },
        }
        for address, state in account_state.items()
    }


def normalize_post_state(postate: FixtureAccountState) -> AccountState:
    # poststate might not be present in some fixtures
    # https://github.com/ethereum/tests/issues/637#issuecomment-534072897
    if postate is None:
        return {}
    else:
        return normalize_account_state(postate)


@to_dict
def normalize_post_state_hash(
    post_state: Dict[str, Any]
) -> Iterable[Tuple[str, bytes]]:
    yield "hash", decode_hex(post_state["hash"])
    if "logs" in post_state:
        yield "logs", decode_hex(post_state["logs"])


@curry
def normalize_statetest_fixture(
    fixture: Dict[str, Any], fork: str, post_state_index: int
) -> Dict[str, Any]:
    post_state = fixture["post"][fork][post_state_index]

    normalized_fixture = {
        "env": normalize_environment(fixture["env"]),
        "pre": normalize_account_state(fixture["pre"]),
        "post": normalize_post_state_hash(post_state),
        "transaction": normalize_unsigned_transaction(
            fixture["transaction"],
            post_state["indexes"],
        ),
    }

    return normalized_fixture


def normalize_exec(exec_params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "origin": to_canonical_address(exec_params["origin"]),
        "address": to_canonical_address(exec_params["address"]),
        "caller": to_canonical_address(exec_params["caller"]),
        "value": to_int(exec_params["value"]),
        "data": decode_hex(exec_params["data"]),
        "gas": to_int(exec_params["gas"]),
        "gasPrice": to_int(exec_params["gasPrice"]),
    }


def normalize_callcreates(
    callcreates: Sequence[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    return [
        {
            "data": decode_hex(created_call["data"]),
            "destination": (
                to_canonical_address(created_call["destination"])
                if created_call["destination"]
                else CREATE_CONTRACT_ADDRESS
            ),
            "gasLimit": to_int(created_call["gasLimit"]),
            "value": to_int(created_call["value"]),
        }
        for created_call in callcreates
    ]


@to_dict
def normalize_vmtest_fixture(fixture: Dict[str, Any]) -> Iterable[Tuple[str, Any]]:
    yield "env", normalize_environment(fixture["env"])
    yield "exec", normalize_exec(fixture["exec"])
    yield "pre", normalize_account_state(fixture["pre"])

    if "post" in fixture:
        yield "post", normalize_account_state(fixture["post"])

    if "callcreates" in fixture:
        yield "callcreates", normalize_callcreates(fixture["callcreates"])

    if "gas" in fixture:
        yield "gas", to_int(fixture["gas"])

    if "out" in fixture:
        yield "out", decode_hex(fixture["out"])

    if "logs" in fixture:
        yield "logs", decode_hex(fixture["logs"])


def normalize_signed_transaction(transaction: Dict[str, Any]) -> Dict[str, Any]:
    normalized_universal_transaction = {
        "data": robust_decode_hex(transaction["data"]),
        "gasLimit": to_int(transaction["gasLimit"]),
        "nonce": to_int(transaction["nonce"]),
        "r": to_int(transaction["r"]),
        "s": to_int(transaction["s"]),
        "v": to_int(transaction["v"]),
        "to": decode_hex(transaction["to"]),
        "value": to_int(transaction["value"]),
    }
    if "type" in transaction:
        type_id = to_int(transaction["type"])
        if type_id == 1:
            custom_fields = {
                "type": type_id,
                "gasPrice": to_int(transaction["gasPrice"]),
                "chainId": to_int(transaction["chainId"]),
            }
        elif type_id == 2:
            custom_fields = {
                "type": type_id,
                "chainId": to_int(transaction["chainId"]),
                "maxFeePerGas": to_int(transaction["maxFeePerGas"]),
                "maxPriorityFeePerGas": to_int(transaction["maxPriorityFeePerGas"]),
            }
        else:
            raise ValidationError(f"Did not recognize transaction type {type_id}")
    else:
        custom_fields = {
            "gasPrice": to_int(transaction["gasPrice"]),
        }

    return merge(normalized_universal_transaction, custom_fields)


@curry
def normalize_transactiontest_fixture(
    fixture: Dict[str, Any], fork: str
) -> Dict[str, Any]:
    normalized_fixture = {}

    fork_data = fixture["result"][fork]

    try:
        normalized_fixture["txbytes"] = decode_hex(fixture["txbytes"])
    except binascii.Error:
        normalized_fixture["rlpHex"] = fixture["txbytes"]

    if "sender" in fork_data:
        normalized_fixture["sender"] = fork_data["sender"]

    if "hash" in fork_data:
        normalized_fixture["hash"] = fork_data["hash"]

    return normalized_fixture


def normalize_block_header(header: Dict[str, Any]) -> Dict[str, Any]:
    normalized_header = {
        "bloom": big_endian_to_int(decode_hex(header["bloom"])),
        "coinbase": to_canonical_address(header["coinbase"]),
        "difficulty": to_int(header["difficulty"]),
        "extraData": decode_hex(header["extraData"]),
        "gasLimit": to_int(header["gasLimit"]),
        "gasUsed": to_int(header["gasUsed"]),
        "hash": decode_hex(header["hash"]),
        "mixHash": decode_hex(header["mixHash"]),
        "nonce": decode_hex(header["nonce"]),
        "number": to_int(header["number"]),
        "parentHash": decode_hex(header["parentHash"]),
        "receiptTrie": decode_hex(header["receiptTrie"]),
        "stateRoot": decode_hex(header["stateRoot"]),
        "timestamp": to_int(header["timestamp"]),
        "transactionsTrie": decode_hex(header["transactionsTrie"]),
        "uncleHash": decode_hex(header["uncleHash"]),
    }
    if "blocknumber" in header:
        normalized_header["blocknumber"] = to_int(header["blocknumber"])
    if "baseFeePerGas" in header:
        normalized_header["baseFeePerGas"] = to_int(header["baseFeePerGas"])
    if "chainname" in header:
        normalized_header["chainname"] = header["chainname"]
    if "chainnetwork" in header:
        normalized_header["chainnetwork"] = header["chainnetwork"]
    return normalized_header


def normalize_block(block: Dict[str, Any]) -> Dict[str, Any]:
    normalized_block: Dict[str, Any] = {}

    try:
        normalized_block["rlp"] = decode_hex(block["rlp"])
    except ValueError as err:
        normalized_block["rlp_error"] = err

    if "blockHeader" in block:
        normalized_block["blockHeader"] = normalize_block_header(block["blockHeader"])
    if "transactions" in block:
        normalized_block["transactions"] = [
            normalize_signed_transaction(transaction)
            for transaction in block["transactions"]
        ]
    if "expectException" in block:
        normalized_block["expectException"] = block["expectException"]
    return normalized_block


def normalize_blockchain_fixtures(fixture: Dict[str, Any]) -> Dict[str, Any]:
    normalized_fixture = {
        "blocks": [
            normalize_block(block_fixture) for block_fixture in fixture["blocks"]
        ],
        "genesisBlockHeader": normalize_block_header(fixture["genesisBlockHeader"]),
        "lastblockhash": decode_hex(fixture["lastblockhash"]),
        "pre": normalize_account_state(fixture["pre"]),
        "postState": normalize_post_state(fixture.get("postState")),
        "network": fixture["network"],
    }

    if "sealEngine" in fixture:
        normalized_fixture["sealEngine"] = fixture["sealEngine"]

    if "genesisRLP" in fixture:
        normalized_fixture["genesisRLP"] = decode_hex(fixture["genesisRLP"])

    return normalized_fixture
