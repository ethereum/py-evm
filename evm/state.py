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
    validate_storage_slot,
)

from evm.utils.keccak import (
    keccak,
)


class StateTrie(object):
    trie = None

    def __init__(self, trie):
        self.trie = trie

    def __setitem__(self, key, value):
        self._set(key, value)

    def _set(self, key, value):
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


class State(object):
    db = None

    def __init__(self, trie):
        self.db = trie.db
        self.state = StateTrie(trie)

    #
    # Base API
    #
    def set_storage(self, address, slot, value):
        validate_is_bytes(value)
        validate_storage_slot(slot)
        validate_canonical_address(address)

        account = self._get_account(address)
        storage = StateTrie(Trie(self.db, account.storage_root))

        if value.strip(b'\x00'):
            encoded_value = rlp.encode(value)
            storage[slot] = encoded_value
        else:
            assert False
            del storage[slot]

        account.storage_root = storage.root_hash
        self.state[address] = rlp.encode(account, sedes=Account)

    def get_storage(self, address, slot):
        validate_canonical_address(address)
        validate_storage_slot(slot)

        account = self._get_account(address)
        storage = StateTrie(Trie(self.db, account.storage_root))

        if slot in storage:
            raw_value = storage[slot]
            return rlp.decode(raw_value)
        else:
            return b''

    def delete_storage(self, address):
        validate_canonical_address(address)

        account = self._get_account(address)
        account.storage_root = BLANK_ROOT_HASH
        self.state[address] = rlp.encode(account, sedes=Account)

    def set_balance(self, address, balance):
        validate_canonical_address(address)
        validate_uint256(balance)

        account = self._get_account(address)
        account.balance = balance

        self.state[address] = rlp.encode(account, sedes=Account)

    def get_balance(self, address):
        validate_canonical_address(address)

        account = self._get_account(address)
        return account.balance

    def set_nonce(self, address, nonce):
        validate_canonical_address(address)
        validate_uint256(nonce)

        account = self._get_account(address)
        account.nonce = nonce

        self.state[address] = rlp.encode(account, sedes=Account)

    def get_nonce(self, address):
        validate_canonical_address(address)

        account = self._get_account(address)
        return account.nonce

    def set_code(self, address, code):
        validate_canonical_address(address)
        validate_is_bytes(code)

        account = self._get_account(address)
        if account.code_hash != EMPTY_SHA3:
            raise ValueError("Should not be overwriting account code")

        account.code_hash = keccak(code)
        self.db[account.code_hash] = code
        self.state[address] = rlp.encode(account, sedes=Account)

    def get_code(self, address):
        validate_canonical_address(address)
        account = self._get_account(address)
        return self.db[account.code_hash]

    def delete_code(self, address):
        validate_canonical_address(address)
        account = self._get_account(address)
        del self.db[account.code_hash]
        account.code_hash = EMPTY_SHA3
        self.state[address] = rlp.encode(account, sedes=Account)

    #
    # Account Methods
    #
    def account_exists(self, address):
        validate_canonical_address(address)
        return address in self.state

    def increment_nonce(self, address):
        current_nonce = self.get_nonce(address)
        self.set_nonce(address, current_nonce + 1)

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
