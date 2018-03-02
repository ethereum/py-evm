import copy
import itertools
import random
import subprocess

from collections.abc import (
    Mapping,
)

from evm.db.backends.memory import MemoryDB

from cytoolz import (
    first,
    merge_with,
)
from eth_utils import (
    to_text,
    int_to_big_endian,
)
from evm.utils.padding import (
    pad32,
)

from eth_keys import keys

try:
    from vyper.compile_lll import (
        compile_to_assembly,
        assembly_to_evm,
    )
    from vyper.parser.parser_utils import LLLnode
except ImportError:
    vyper_available = False
else:
    vyper_available = True


random.seed(0)


def merge_if_dicts(values):
    if all(isinstance(item, Mapping) for item in values):
        return merge_with(merge_if_dicts, *values)
    else:
        return values[-1]


def deep_merge(*dicts):
    return merge_with(merge_if_dicts, *dicts)


def is_cleanly_mergable(*dicts):
    """Check that nothing will be overwritten when dictionaries are merged using `deep_merge`.

    Examples:

        >>> is_cleanly_mergable({"a": 1}, {"b": 2}, {"c": 3})
        True
        >>> is_cleanly_mergable({"a": 1}, {"b": 2}, {"a": 0, c": 3})
        False
        >>> is_cleanly_mergable({"a": 1, "b": {"ba": 2}}, {"c": 3, {"b": {"bb": 4}})
        True
        >>> is_cleanly_mergable({"a": 1, "b": {"ba": 2}}, {"b": {"ba": 4}})
        False

    """
    if len(dicts) <= 1:
        return True
    elif len(dicts) == 2:
        if not all(isinstance(d, Mapping) for d in dicts):
            return False
        else:
            shared_keys = set(dicts[0].keys()) & set(dicts[1].keys())
            return all(is_cleanly_mergable(dicts[0][key], dicts[1][key]) for key in shared_keys)
    else:
        dict_combinations = itertools.combinations(dicts, 2)
        return all(is_cleanly_mergable(*combination) for combination in dict_combinations)


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


def get_version_from_git():
    version = subprocess.check_output(["git", "describe"]).strip()
    return to_text(version)


def calc_state_root(state, account_state_db_class):
    state_db = account_state_db_class(MemoryDB())
    state_db.apply_state_dict(state)
    return state_db.root_hash


def generate_random_keypair():
    key_object = keys.PrivateKey(pad32(int_to_big_endian(random.getrandbits(8 * 32))))
    return key_object.to_bytes(), key_object.public_key.to_canonical_address()


def generate_random_address():
    _, address = generate_random_keypair()
    return address


def compile_vyper_lll(vyper_code):
    if vyper_available:
        lll_node = LLLnode.from_list(vyper_code)
        assembly = compile_to_assembly(lll_node)
        code = assembly_to_evm(assembly)
        return code
    else:
        raise ImportError("Vyper package not installed")


def get_test_name(filler):
    assert len(filler) == 1
    return first(filler)
