import copy
import collections

from evm.validation import (
    validate_is_bytes,
    validate_uint256,
    validate_word,
    validate_canonical_address,
)

from .base import BaseMachineStorage


class MemoryStorage(BaseMachineStorage):
    balances = None
    nonces = None
    storage = None
    code = None

    def __init__(self):
        self.storage = collections.defaultdict(dict)
        self.balances = {}
        self.nonces = {}
        self.code = {}

    def set_storage(self, account, slot, value):
        validate_is_bytes(value)
        validate_uint256(slot)
        validate_canonical_address(account)
        self.storage[account][slot] = value

    def get_storage(self, account, slot):
        validate_canonical_address(account)
        validate_uint256(slot)
        return self.storage[account].get(slot, b'')

    def delete_storage(self, account):
        validate_canonical_address(account)
        self.storage[account] = {}

    def set_balance(self, account, balance):
        validate_canonical_address(account)
        validate_uint256(balance)
        self.balances[account] = balance

    def get_balance(self, account):
        validate_canonical_address(account)
        return self.balances.get(account, 0)

    def set_nonce(self, account, nonce):
        validate_canonical_address(account)
        validate_uint256(nonce)
        self.nonces[account] = nonce

    def get_nonce(self, account):
        validate_canonical_address(account)
        return self.nonces.get(account, 0)

    def set_code(self, account, code):
        validate_canonical_address(account)
        validate_is_bytes(code)
        self.code[account] = code

    def get_code(self, account):
        validate_canonical_address(account)
        return self.code.get(account, b'')

    def delete_code(self, account):
        validate_canonical_address(account)
        self.code[account] = b''

    def snapshot(self):
        return {
            'storage': copy.deepcopy(self.storage),
            'balances': copy.deepcopy(self.balances),
            'nonces': copy.deepcopy(self.nonces),
            'code': copy.deepcopy(self.code),
        }

    def revert(self, snapshot):
        self.storage = snapshot['storage']
        self.balances = snapshot['balances']
        self.nonces = snapshot['nonces']
        self.code = snapshot['code']
