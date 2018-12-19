import copy
import random

from typing import (
    Any,
    Dict,
    List,
    Tuple,
    Type,
)

from eth_typing import (
    Address,
)

from eth_utils import (
    int_to_big_endian,
)

from eth.db.backends.memory import MemoryDB
from eth.db.account import BaseAccountDB

from eth.typing import (
    AccountState,
    TransactionDict,
)

from eth._utils.db import (
    apply_state_dict,
)
from eth._utils.padding import (
    pad32,
)

from eth_keys import keys


def wrap_in_list(item: Any) -> List[Any]:
    return [item]


def add_transaction_to_group(group: Dict[str, Any],
                             transaction: TransactionDict) -> Tuple[Dict[str, Any], Dict[str, int]]:

    for key in ["gasPrice", "nonce", "secretKey", "to"]:
        if key in transaction and transaction[key] != group[key]:   # type: ignore # https://github.com/python/mypy/issues/5359 # noqa: 501
            raise ValueError("Can't add transaction as it differs in {}".format(key))

    new_group = copy.deepcopy(group)
    indexes = {}
    for key, index_key in [("data", "data"), ("gasLimit", "gas"), ("value", "value")]:
        if key in group:
            if key not in transaction:
                if len(new_group[key]) != 1:
                    raise ValueError("Can't add transaction as {} is ambiguous".format(key))
                index = 0
            else:
                if transaction[key] not in new_group[key]:      # type: ignore # https://github.com/python/mypy/issues/5359 # noqa: 501
                    new_group[key].append(transaction[key])     # type: ignore # https://github.com/python/mypy/issues/5359 # noqa: 501
                index = new_group[key].index(transaction[key])  # type: ignore # https://github.com/python/mypy/issues/5359 # noqa: 501
            indexes[index_key] = index
        else:
            assert key not in transaction
    return new_group, indexes


def calc_state_root(state: AccountState, account_db_class: Type[BaseAccountDB]) -> bytes:
    account_db = account_db_class(MemoryDB())
    apply_state_dict(account_db, state)
    return account_db.state_root


def generate_random_keypair() -> Tuple[bytes, Address]:
    key_object = keys.PrivateKey(pad32(int_to_big_endian(random.getrandbits(8 * 32))))
    return key_object.to_bytes(), Address(key_object.public_key.to_canonical_address())


def generate_random_address() -> Address:
    _, address = generate_random_keypair()
    return address
