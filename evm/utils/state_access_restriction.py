from eth_utils import (
    to_set,
)

from evm.constants import (
    NONCE_TRIE_PREFIX,
    BALANCE_TRIE_PREFIX,
    CODE_TRIE_PREFIX,
    STORAGE_TRIE_PREFIX,
)

from evm.utils.keccak import (
    keccak,
)


def is_accessible(address, slot_as_key, access_prefix_list):
    """Check if a storage slot is specified in an access prefix list."""
    key = keccak(address) + STORAGE_TRIE_PREFIX + slot_as_key
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

    for prefix in sorted(prefix_list, key=lambda prefix: len(prefix)):
        cur = root

        for i in range(len(prefix)):
            if None in cur:
                break

            if prefix[i] not in cur:
                cur[prefix[i]] = {}

            if i == len(prefix)-1:
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
        yield keccak(address) + NONCE_TRIE_PREFIX
        yield keccak(address) + BALANCE_TRIE_PREFIX
        yield keccak(address) + CODE_TRIE_PREFIX
        for prefix in remove_redundant_prefixes(storage_prefixes):
            yield keccak(address) + STORAGE_TRIE_PREFIX + prefix
