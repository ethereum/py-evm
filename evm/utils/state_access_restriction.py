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


def to_prefix_list_form(access_list):
    """Expand an access list to a flat list of storage key prefixes.

    As input a list of the form `[[address, prefix1, prefix2, ...], ...]` is expected.
    """
    prefix_list = []
    for obj in access_list:
        address, storage_prefixes = obj[0], obj[1:]
        prefix_list.append(keccak(address) + NONCE_TRIE_PREFIX)
        prefix_list.append(keccak(address) + BALANCE_TRIE_PREFIX)
        prefix_list.append(keccak(address) + CODE_TRIE_PREFIX)
        for prefix in storage_prefixes:
            prefix_list.append(keccak(address) + STORAGE_TRIE_PREFIX + prefix)
    # TODO: remove duplicates/redundancies?
    return prefix_list
