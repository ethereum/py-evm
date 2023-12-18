from collections import (
    namedtuple,
)
from functools import (
    partial,
    wraps,
)
from typing import (
    Any,
    Callable,
    Dict,
    Optional,
)

from eth_utils import (
    apply_formatters_to_dict,
    decode_hex,
    to_canonical_address,
)
from eth_utils.toolz import (
    assoc,
    assoc_in,
    curry,
    merge,
)

from eth.tools._utils.mappings import (
    deep_merge,
)
from eth.tools._utils.normalization import (
    normalize_environment,
    normalize_execution,
    normalize_networks,
    normalize_state,
    normalize_transaction,
)
from eth.tools._utils.vyper import (
    compile_vyper_lll,
)
from eth.tools.fixtures.helpers import (
    get_test_name,
)
from eth.typing import (
    GeneralState,
    TransactionDict,
)

from ._utils import (
    add_transaction_to_group,
    wrap_in_list,
)

#
# Defaults
#

DEFAULT_MAIN_ENVIRONMENT = {
    "currentCoinbase": to_canonical_address(
        "0x2adc25665018aa1fe0e6bc666dac8fc2697ff9ba"
    ),
    "currentDifficulty": 131072,
    "currentGasLimit": 1000000,
    "currentNumber": 1,
    "currentTimestamp": 1000,
    "previousHash": decode_hex(
        "0x5e20a0453cecd065ea59c37ac63e079ee08998b6045136a8ce6635c7912ec0b6"
    ),
}


DEFAULT_MAIN_TRANSACTION: TransactionDict = {
    "data": b"",
    "gasLimit": 100000,
    "gasPrice": 0,
    "nonce": 0,
    "secretKey": decode_hex(
        "0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8"
    ),
    "to": to_canonical_address("0x0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6"),
    "value": 0,
}


def get_default_transaction(networks: Any) -> TransactionDict:
    return DEFAULT_MAIN_TRANSACTION


DEFAULT_EXECUTION = {
    "address": to_canonical_address("0x0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6"),
    "origin": to_canonical_address("0xcd1722f2947def4cf144679da39c4c32bdc35681"),
    "caller": to_canonical_address("0xcd1722f2947def4cf144679da39c4c32bdc35681"),
    "value": 1000000000000000000,
    "data": b"",
    "gasPrice": 1,
    "gas": 100000,
}


Test = namedtuple("Test", ["filler", "fill_kwargs"])
# make `None` default for fill_kwargs
Test.__new__.__defaults__ = (None,)


#
# Filler Generation
#


def setup_filler(
    name: str, environment: Optional[Dict[Any, Any]] = None
) -> Dict[str, Dict[str, Any]]:
    environment = normalize_environment(environment or {})
    return {
        name: {
            "env": environment,
            "pre": {},
        }
    }


def setup_main_filler(
    name: str, environment: Optional[Dict[Any, Any]] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Kick off the filler generation process by creating the general filler scaffold with
    a test name and general information about the testing environment.

    For tests for the main chain, the `environment` parameter is expected to be a
    dictionary with some or all of the following keys:

    +------------------------+---------------------------------+
    | key                    | description                     |
    +========================+=================================+
    | ``"currentCoinbase"``  | the coinbase address            |
    +------------------------+---------------------------------+
    | ``"currentNumber"``    | the block number                |
    +------------------------+---------------------------------+
    | ``"previousHash"``     | the hash of the parent block    |
    +------------------------+---------------------------------+
    | ``"currentDifficulty"``| the block's difficulty          |
    +------------------------+---------------------------------+
    | ``"currentGasLimit"``  | the block's gas limit           |
    +------------------------+---------------------------------+
    | ``"currentTimestamp"`` | the timestamp of the block      |
    +------------------------+---------------------------------+
    """
    return setup_filler(name, merge(DEFAULT_MAIN_ENVIRONMENT, environment or {}))


def pre_state(*raw_state: GeneralState, filler: Dict[str, Any]) -> None:
    """
    Specify the state prior to the test execution. Multiple invocations don't override
    the state but extend it instead.

    In general, the elements of `state_definitions` are nested dictionaries of the
    following form:

    .. code-block:: python

        {
            address: {
                "nonce": <account nonce>,
                "balance": <account balance>,
                "code": <account code>,
                "storage": {
                    <storage slot>: <storage value>
                }
            }
        }

    To avoid unnecessary nesting especially if only few fields per account are
    specified, the following and similar formats are possible as well:

    .. code-block:: python

        (address, "balance", <account balance>)
        (address, "storage", <storage slot>, <storage value>)
        (address, "storage", {<storage slot>: <storage value>})
        (address, {"balance", <account balance>})
    """

    @wraps(pre_state)
    def _pre_state(filler: Dict[str, Any]) -> Dict[str, Any]:
        test_name = get_test_name(filler)

        old_pre_state = filler[test_name].get("pre_state", {})
        pre_state = normalize_state(raw_state)
        defaults = {
            address: {
                "balance": 0,
                "nonce": 0,
                "code": b"",
                "storage": {},
            }
            for address in pre_state
        }
        new_pre_state = deep_merge(defaults, old_pre_state, pre_state)

        return assoc_in(filler, [test_name, "pre"], new_pre_state)


def _expect(
    post_state: Dict[str, Any],
    networks: Any,
    transaction: TransactionDict,
    filler: Dict[str, Any],
) -> Dict[str, Any]:
    test_name = get_test_name(filler)
    test = filler[test_name]
    test_update: Dict[str, Dict[Any, Any]] = {test_name: {}}

    pre_state = test.get("pre", {})
    post_state = normalize_state(post_state or {})
    defaults = {
        address: {
            "balance": 0,
            "nonce": 0,
            "code": b"",
            "storage": {},
        }
        for address in post_state
    }
    result = deep_merge(defaults, pre_state, normalize_state(post_state))
    new_expect = {"result": result}

    if transaction is not None:
        transaction = normalize_transaction(
            merge(get_default_transaction(networks), transaction)
        )
        if "transaction" not in test:
            transaction_group = apply_formatters_to_dict(
                {
                    "data": wrap_in_list,
                    "gasLimit": wrap_in_list,
                    "value": wrap_in_list,
                },
                transaction,
            )
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
        test_update = assoc_in(
            test_update, [test_name, "transaction"], transaction_group
        )

    if networks is not None:
        networks = normalize_networks(networks)
        new_expect = assoc(new_expect, "networks", networks)

    existing_expects = test.get("expect", [])
    expect = existing_expects + [new_expect]
    test_update = assoc_in(test_update, [test_name, "expect"], expect)

    return deep_merge(filler, test_update)


def expect(
    post_state: Optional[Dict[str, Any]] = None,
    networks: Optional[Any] = None,
    transaction: Optional[TransactionDict] = None,
) -> Callable[..., Dict[str, Any]]:
    """
    Specify the expected result for the test.

    For state tests, multiple expectations can be given, differing in the transaction
    data, gas limit, and value, in the applicable networks, and as a result also in the
    post state. VM tests support only a single expectation with no specified network and
    no transaction.
    (here, its role is played by :func:`~eth.tools.fixtures.fillers.execution`).

    * ``post_state`` is a list of state definition in the same form as expected
      by :func:`~eth.tools.fixtures.fillers.pre_state`. State items that are
      not set explicitly default to their pre state.

    * ``networks`` defines the forks under which the expectation is applicable. It
        should be a sublist of the following identifiers
        (also available in `ALL_FORKS`):

      * ``"Frontier"``
      * ``"Homestead"``
      * ``"EIP150"``
      * ``"EIP158"``
      * ``"Byzantium"``

    * ``transaction`` is a dictionary coming in two variants. For the main shard:

      +----------------+-------------------------------+
      | key            | description                   |
      +================+===============================+
      | ``"data"``     | the transaction data,         |
      +----------------+-------------------------------+
      | ``"gasLimit"`` | the transaction gas limit,    |
      +----------------+-------------------------------+
      | ``"gasPrice"`` | the gas price,                |
      +----------------+-------------------------------+
      | ``"nonce"``    | the transaction nonce,        |
      +----------------+-------------------------------+
      | ``"value"``    | the transaction value         |
      +----------------+-------------------------------+

    In addition, one should specify either the signature itself (via keys ``"v"``,
    ``"r"``, and ``"s"``) or a private key used for signing (via ``"secretKey"``).
    """
    return partial(_expect, post_state, networks, transaction)


@curry
def execution(execution: Dict[str, Any], filler: Dict[str, Any]) -> Dict[str, Any]:
    """
    For VM tests, specify the code that is being run as well as the current state of
    the EVM. State tests don't support this object. The parameter is a dictionary
    specifying some or all of the following keys:

    +--------------------+------------------------------------------------------------+
    |  key               | description                                                |
    +====================+============================================================+
    | ``"address"``      | the address of the account executing the code              |
    +--------------------+------------------------------------------------------------+
    | ``"caller"``       | the caller address                                         |
    +--------------------+------------------------------------------------------------+
    | ``"origin"``       | the origin address (defaulting to the caller address)      |
    +--------------------+------------------------------------------------------------+
    | ``"value"``        | the value of the call                                      |
    +--------------------+------------------------------------------------------------+
    | ``"data"``         | the data passed with the call                              |
    +--------------------+------------------------------------------------------------+
    | ``"gasPrice"``     | the gas price of the call                                  |
    +--------------------+------------------------------------------------------------+
    | ``"gas"``          | the amount of gas allocated for the call                   |
    +--------------------+------------------------------------------------------------+
    | ``"code"``         | the bytecode to execute                                    |
    +--------------------+------------------------------------------------------------+
    | ``"vyperLLLCode"`` | the code in Vyper LLL (compiled to bytecode automatically) |
    +--------------------+------------------------------------------------------------+
    """
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
        },
    )
