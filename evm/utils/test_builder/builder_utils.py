import copy
import random
import subprocess

from collections.abc import (
    Mapping,
)

from evm.db.backends.memory import MemoryDB

from eth_utils import (
    force_text,
    int_to_big_endian,
)

from eth_keys import keys


def merge_nested(*dicts):
    result = {}
    for d in dicts:
        for key, value in d.items():
            if key not in result:
                result[key] = value  # keep key-value pair if there's no conflict
            elif not isinstance(value, Mapping) or not isinstance(result[key], Mapping):
                result[key] = value  # use value of later dict if are not mergeable
            else:
                result[key] = merge_nested(result[key], value)  # merge if both are dicts
    return result


def wrap_in_list(item):
    return [item]


def add_transaction_to_group(group, transaction):
    for key in ["gasPrice", "nonce", "secretKey", "to"]:
        if key in transaction and transaction[key] != group[key]:
            raise ValueError("Can't add transaction as it differs in {}".format(key))

    new_group = copy.deepcopy(group)
    indexes = {}
    for key, index_key in [("data", "data"), ("gasLimit", "gas"), ("value", "value")]:
        if key not in transaction:
            if len(new_group[key]) != 1:
                raise ValueError("Can't add transaction as {} is ambiguous".format(key))
            index = 0
        else:
            if transaction[key] not in new_group[key]:
                new_group[key].append(transaction[key])
            index = new_group[key].index(transaction[key])
        indexes[index_key] = index
    return new_group, indexes


def get_version_from_git():
    version = subprocess.check_output(["git", "describe"]).strip()
    return force_text(version)


def calc_state_root(state, account_state_db_class):
    state_db = account_state_db_class(MemoryDB())
    state_db.apply_state_dict(state)
    return state_db.root_hash


def generate_random_keypair():
    key_object = keys.PrivateKey(int_to_big_endian(random.getrandbits(8 * 32)))
    return key_object.to_bytes(), key_object.public_key.to_canonical_address()


def generate_random_address():
    _, address = generate_random_keypair()
    return address
