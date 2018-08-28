import copy
import random

from eth_utils import (
    int_to_big_endian,
)

from eth.db.backends.memory import MemoryDB

from eth.utils.db import (
    apply_state_dict,
)
from eth.utils.padding import (
    pad32,
)

from eth_keys import keys


def wrap_in_list(item):
    return [item]


def add_transaction_to_group(group, transaction):
    for key in ["gasPrice", "nonce", "secretKey", "to"]:
        if key in transaction and transaction[key] != group[key]:
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
                if transaction[key] not in new_group[key]:
                    new_group[key].append(transaction[key])
                index = new_group[key].index(transaction[key])
            indexes[index_key] = index
        else:
            assert key not in transaction
    return new_group, indexes


def calc_state_root(state, account_db_class):
    account_db = account_db_class(MemoryDB())
    apply_state_dict(account_db, state)
    return account_db.state_root


def generate_random_keypair():
    key_object = keys.PrivateKey(pad32(int_to_big_endian(random.getrandbits(8 * 32))))
    return key_object.to_bytes(), key_object.public_key.to_canonical_address()


def generate_random_address():
    _, address = generate_random_keypair()
    return address
