import logging

import rlp

from trie import (
    Trie
)

from evm.constants import (
    BLANK_ROOT_HASH,
    EMPTY_SHA3,
)
from evm.rlp.accounts import (
    Account,
)
from evm.validation import (
    validate_is_bytes,
    validate_uint256,
    validate_canonical_address,
)

from evm.utils.keccak import (
    keccak,
)
from evm.utils.numeric import (
    int_to_big_endian,
)
from evm.utils.padding import (
    pad32,
)


class StateTrie(object):
    trie = None

    logger = logging.getLogger('evm.state.StateTrie')

    def __init__(self, trie):
        self.trie = trie

    def __setitem__(self, key, value):
        self._set(key, value)

    def _set(self, key, value):
        # TODO: remove, for debug purposes.
        self.trie[keccak(key)] = value

    def __getitem__(self, key):
        return self.trie[keccak(key)]

    def __delitem__(self, key):
        del self.trie[keccak(key)]

    def __contains__(self, key):
        return keccak(key) in self.trie

    @property
    def root_hash(self):
        return self.trie.root_hash

    def snapshot(self):
        return self.trie.snapshot()

    def revert(self, snapshot):
        return self.trie.revert(snapshot)


class State(object):
    """
    High level API around account storage.
    """
    db = None
    state = None

    logger = logging.getLogger('evm.state.State')

    def __init__(self, db, root_hash):
        self.db = db
        self.state = StateTrie(Trie(db, root_hash))

        orig_set = self.state._set

        def wrapper(key, value):
            from eth_utils import encode_hex
            before_acct = self._get_account(key)
            #print('ACCT BEFORE', encode_hex(key)[2:12], encode_hex(before_acct.storage_root)[2:12])
            after_acct = rlp.decode(value, sedes=Account)
            #print('ACCT AFTER', encode_hex(key)[2:12], encode_hex(after_acct.storage_root)[2:12])
            orig_set(key, value)
        self.state._set = wrapper

    #
    # Base API
    #
    def set_storage(self, address, slot, value):
        validate_uint256(value)
        validate_uint256(slot)
        validate_canonical_address(address)

        account = self._get_account(address)
        storage = StateTrie(Trie(self.db, account.storage_root))

        slot_as_key = pad32(int_to_big_endian(slot))

        if value:
            encoded_value = rlp.encode(value)
            storage[slot_as_key] = encoded_value
        else:
            del storage[slot_as_key]

        account.storage_root = storage.root_hash
        self._set_account(address, account)

    def get_storage(self, address, slot):
        validate_canonical_address(address)
        validate_uint256(slot)

        account = self._get_account(address)
        storage = StateTrie(Trie(self.db, account.storage_root))

        slot_as_key = pad32(int_to_big_endian(slot))

        if slot_as_key in storage:
            encoded_value = storage[slot_as_key]
            return rlp.decode(encoded_value, sedes=rlp.sedes.big_endian_int)
        else:
            return 0

    def delete_storage(self, address):
        validate_canonical_address(address)

        account = self._get_account(address)
        account.storage_root = BLANK_ROOT_HASH
        self._set_account(address, account)

    def set_balance(self, address, balance):
        validate_canonical_address(address)
        validate_uint256(balance)

        account = self._get_account(address)
        account.balance = balance

        self._set_account(address, account)

    def get_balance(self, address):
        validate_canonical_address(address)

        account = self._get_account(address)
        return account.balance

    def set_nonce(self, address, nonce):
        validate_canonical_address(address)
        validate_uint256(nonce)

        account = self._get_account(address)
        account.nonce = nonce

        self._set_account(address, account)

    def get_nonce(self, address):
        validate_canonical_address(address)

        account = self._get_account(address)
        return account.nonce

    def set_code(self, address, code):
        validate_canonical_address(address)
        validate_is_bytes(code)

        account = self._get_account(address)

        account.code_hash = keccak(code)
        self.db[account.code_hash] = code
        self._set_account(address, account)

    def get_code(self, address):
        validate_canonical_address(address)
        account = self._get_account(address)
        try:
            return self.db[account.code_hash]
        except KeyError:
            return b''

    def delete_code(self, address):
        validate_canonical_address(address)
        account = self._get_account(address)
        del self.db[account.code_hash]
        account.code_hash = EMPTY_SHA3
        self._set_account(address, account)

    #
    # Account Methods
    #
    def delete_account(self, address):
        del self.state[address]

    def account_exists(self, address):
        validate_canonical_address(address)
        return bool(self.state[address])

    def touch_account(self, address):
        account = self._get_account(address)
        self._set_account(address, account)

    def increment_nonce(self, address):
        current_nonce = self.get_nonce(address)
        self.set_nonce(address, current_nonce + 1)

    #
    # Internal
    #
    def snapshot(self):
        return self.state.snapshot()

    def revert(self, snapshot):
        return self.state.revert(snapshot)

    #
    # Internal
    #
    def _get_account(self, address):
        if address in self.state:
            account = rlp.decode(self.state[address], sedes=Account)
            account._mutable = True
        else:
            account = Account()
        return account

    def _set_account(self, address, account):
        self.state[address] = rlp.encode(account, sedes=Account)
