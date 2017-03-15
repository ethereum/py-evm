import collections

from evm.validation import (
    validate_is_bytes,
    validate_uint256,
    validate_canonical_address,
)

from .base import BaseMachineStorage


class MemoryStorage(BaseMachineStorage):
    balances = None
    nonces = None
    storage = None
    code = None

    def __init__(self):
        self.storage = collections.defaultdict(
            lambda: collections.defaultdict(lambda: b'')
        )
        self.balances = collections.defaultdict(int)
        self.nonces = collections.defaultdict(int)
        self.code = collections.defaultdict(bytes)

    def set_storage(self, account, slot, value):
        validate_is_bytes(value)
        validate_uint256(slot)
        validate_canonical_address(account)
        self.storage[account][slot] = value

    def get_storage(self, account, slot):
        validate_canonical_address(account)
        validate_uint256(slot)
        return self.storage[account][slot]

    def set_balance(self, account, balance):
        validate_canonical_address(account)
        validate_uint256(balance)
        self.balances[account] = balance

    def get_balance(self, account):
        validate_canonical_address(account)
        return self.balances[account]

    def set_nonce(self, account, nonce):
        validate_canonical_address(account)
        validate_uint256(nonce)
        self.nonces[account] = nonce

    def get_nonce(self, account):
        validate_canonical_address(account)
        return self.nonces[account]

    def set_code(self, account, code):
        validate_canonical_address(account)
        validate_is_bytes(code)
        self.code[account] = code

    def get_code(self, account):
        validate_canonical_address(account)
        return self.code[account]
