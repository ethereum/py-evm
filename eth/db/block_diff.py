from collections import defaultdict
from typing import (
    cast,
    Dict,
    Iterable,
    NamedTuple,
    Optional,
    Tuple,
)

from eth_typing import (
    Address,
    Hash32,
)
import rlp

from eth.db.backends.base import BaseDB
from eth.db.schema import SchemaTurbo
from eth.rlp.accounts import Account


class Change(NamedTuple):
    old: object
    new: object


class BlockDiff:
    """
    TODO: I'm not sure where this class belongs
    """

    def __init__(self, block_hash: Hash32) -> None:
        self.block_hash = block_hash

        self.changed_accounts: Dict[Address, Change] = dict()
        self.changed_storage_items: Dict[Address, Dict[int, Change]] = defaultdict(dict)

    def set_account_changed(self, address: Address, old: bytes, new: bytes) -> None:
        self.changed_accounts[address] = Change(old, new)

    def set_storage_changed(self, address: Address, slot: int, old: bytes, new: bytes) -> None:
        self.changed_storage_items[address][slot] = Change(old, new)

    def get_changed_accounts(self) -> Iterable[Address]:
        return tuple(
            set(self.changed_accounts.keys()) | set(self.changed_storage_items.keys())
        )

    def get_changed_storage_items(self) -> Iterable[Tuple[Address, int, int, int]]:
        def storage_items_to_diff(item: Dict[int, Change]) -> Iterable[Tuple[int, int, int]]:
            return [
                (key, cast(int, change.old), cast(int, change.new))
                for key, change in item.items()
            ]

        return [
            (acct, key, old_value, new_value)
            for acct, value in self.changed_storage_items.items()
            for key, old_value, new_value in storage_items_to_diff(value)
        ]

    def get_account(self, address: Address, new: bool = True) -> bytes:
        change = self.changed_accounts[address]
        return cast(bytes, change.new) if new else cast(bytes, change.old)

    def get_decoded_account(self, address: Address, new: bool = True) -> Optional[Account]:
        encoded = self.get_account(address, new)
        if encoded == b'':
            return None  # this means the account used to or currently does not exist
        return rlp.decode(encoded, sedes=Account)

    @classmethod
    def from_db(cls, db: BaseDB, block_hash: Hash32) -> 'BlockDiff':
        """
        KeyError is thrown if a diff was not saved for the provided {block_hash}
        """

        encoded_diff = db[SchemaTurbo.make_block_diff_lookup_key(block_hash)]
        diff = rlp.decode(encoded_diff)

        accounts, storage_items = diff

        block_diff = cls(block_hash)

        for key, old, new in accounts:
            block_diff.set_account_changed(key, old, new)

        for key, slot, old, new in storage_items:
            block_diff.set_storage_changed(key, slot, old, new)

        return block_diff

    def write_to(self, db: BaseDB) -> None:

        # TODO: this should probably verify that the state roots have all been added

        accounts = [
            [key, value.old, value.new]
            for key, value in self.changed_accounts.items()
        ]

        storage_items = self.get_changed_storage_items()

        diff = [
            accounts,
            storage_items
        ]

        encoded_diff = rlp.encode(diff)
        db[SchemaTurbo.make_block_diff_lookup_key(self.block_hash)] = encoded_diff
