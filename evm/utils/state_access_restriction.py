from eth_utils import (
    keccak,
    to_set,
)

from evm.constants import (
    BALANCE_TRIE_PREFIX,
    CODE_TRIE_PREFIX,
    STORAGE_TRIE_PREFIX,
)

from evm.utils.padding import (
    pad32,
)
from evm.utils.numeric import (
    int_to_big_endian,
)


def is_accessible(key, access_prefix_list):
    """Check if a key is specified in an access prefix list."""
    for prefix in access_prefix_list:
        if key.startswith(prefix):
            return True
    return False


@to_set
def remove_redundant_prefixes(prefix_list):
    """Given a list of strings, this removes redundant strings that are covered
    by other strings in the list. For example, given `["eth", "ethereum"]`,
    this function will return just `["eth"]` as it's sufficient to match all
    strings that are covered by both `eth` and `ethereum`.
    """
    root = {}

    if b'' in prefix_list:
        yield b''
    else:
        sorted_prefixes = sorted(prefix_list, key=lambda prefix: len(prefix))
        for prefix in sorted_prefixes:
            cur = root

            for i in range(len(prefix)):
                if None in cur:
                    break

                if prefix[i] not in cur:
                    cur[prefix[i]] = {}

                if i == len(prefix) - 1:
                    cur[prefix[i]][None] = {}
                    yield prefix

                cur = cur[prefix[i]]


@to_set
def to_prefix_list_form(access_list):
    """Expand an access list to a flat list of storage key prefixes.

    As input a list of the form `[[address, prefix1, prefix2, ...], ...]` is expected.
    """
    for obj in access_list:
        address, *storage_prefixes = obj
        yield get_balance_key(address)
        yield get_code_key(address)
        for prefix in remove_redundant_prefixes(storage_prefixes):
            yield keccak(address) + STORAGE_TRIE_PREFIX + prefix


def get_storage_key(address, slot):
    return keccak(address) + STORAGE_TRIE_PREFIX + pad32(int_to_big_endian(slot))


def get_full_storage_key(address):
    return keccak(address) + STORAGE_TRIE_PREFIX


def get_balance_key(address):
    return keccak(address) + BALANCE_TRIE_PREFIX


def get_code_key(address):
    return keccak(address) + CODE_TRIE_PREFIX
