from collections import defaultdict
from typing import (
    Dict,
    Iterable,
    Optional,
    Set,
    Tuple,
)

from eth_typing import (
    Address,
    Hash32,
)
from eth_utils import (
    big_endian_to_int,
    to_tuple
)
import rlp

from eth.db.backends.base import BaseDB
from eth.db.atomic import AtomicDB
from eth.db.schema import SchemaTurbo, Schemas, get_schema
from eth.rlp.accounts import Account


"""
TODO: Decide on the best interface for returning changes:
- diff.get_slot_change() -> [old, new]
- diff.get_slot_change(new=FAlse) -> old
- diff.get_slot_change(kind=BlockDiff.OLD) -> old
- diff.get_old_slot_value() & diff.get_new_slot_value()
"""


class BlockDiff:

    def __init__(self) -> None:
        self.old_account_values: Dict[Address, Optional[bytes]] = dict()
        self.new_account_values: Dict[Address, Optional[bytes]] = dict()

        SLOT_TO_VALUE = Dict[int, bytes]
        self.old_storage_items: Dict[Address, SLOT_TO_VALUE] = defaultdict(dict)
        self.new_storage_items: Dict[Address, SLOT_TO_VALUE] = defaultdict(dict)

    def set_account_changed(self, address: Address, old_value: bytes, new_value: bytes) -> None:
        self.old_account_values[address] = old_value
        self.new_account_values[address] = new_value

    def set_storage_changed(self, address: Address, slot: int,
                            old_value: bytes, new_value: bytes) -> None:
        self.old_storage_items[address][slot] = old_value
        self.new_storage_items[address][slot] = new_value

    def get_changed_accounts(self) -> Set[Address]:
        return set(self.old_account_values.keys()) | set(self.old_storage_items.keys())

    @to_tuple
    def get_changed_storage_items(self) -> Iterable[Tuple[Address, int, bytes, bytes]]:
        for address in self.old_storage_items.keys():
            new_items = self.new_storage_items[address]
            old_items = self.old_storage_items[address]
            for slot in old_items.keys():
                yield address, slot, old_items[slot], new_items[slot]

    def get_changed_slots(self, address: Address) -> Set[int]:
        """
        Returns which slots changed for the given account.
        """
        if address not in self.old_storage_items.keys():
            return set()

        return set(self.old_storage_items[address].keys())

    def get_slot_change(self, address: Address, slot: int) -> Tuple[int, int]:
        if address not in self.old_storage_items:
            raise Exception(f'account {address} did not change')
        old_values = self.old_storage_items[address]

        if slot not in old_values:
            raise Exception(f"{address}'s slot {slot} did not change")

        new_values = self.new_storage_items[address]
        return big_endian_to_int(old_values[slot]), big_endian_to_int(new_values[slot])

    def get_account(self, address: Address, new: bool = True) -> bytes:
        dictionary = self.new_account_values if new else self.old_account_values
        return dictionary[address]

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

        block_diff = cls()

        for key, old, new in accounts:
            block_diff.set_account_changed(key, old, new)

        for key, slot, old, new in storage_items:
            decoded_slot = big_endian_to_int(slot)  # rlp.encode turns our ints into bytes
            block_diff.set_storage_changed(key, decoded_slot, old, new)

        return block_diff

    def write_to(self, db: BaseDB, block_hash: Hash32) -> None:

        # TODO: this should probably verify that the state roots have all been added

        accounts = [
            [address, self.old_account_values[address], self.new_account_values[address]]
            for address in self.old_account_values.keys()
        ]

        storage_items = self.get_changed_storage_items()

        diff = [
            accounts,
            storage_items
        ]

        encoded_diff = rlp.encode(diff)
        db[SchemaTurbo.make_block_diff_lookup_key(block_hash)] = encoded_diff

    @classmethod
    def apply_to(cls, db: BaseDB,
                 parent_hash: Hash32, block_hash: Hash32, forward: bool = True) -> None:
        """
        Looks up the BlockDif for the given hash and applies it to the databae
        """

        if get_schema(db) != Schemas.TURBO:
            return

        # 1. Verify the database is in the correct state
        if forward:
            assert db[SchemaTurbo.current_state_lookup_key] == parent_hash
        else:
            assert db[SchemaTurbo.current_state_lookup_key] == block_hash

        # 2. Lookup the diff (throws KeyError if it does not exist)
        diff = cls.from_db(db, block_hash)

        # Sadly, AtomicDB.atomic_batch() databases are not themselves atomic, so the rest
        # of this method cannot be wrapped in an atomic_batch context manager.

        # TODO: also keep track of storage items!
        for address in diff.get_changed_accounts():
            old_value = diff.get_account(address, new=False)
            new_value = diff.get_account(address, new=True)

            key = SchemaTurbo.make_account_state_lookup_key(keccak(address))

            if forward:
                assert db[key] == old_value
                db[key] = new_value
            else:
                assert db[key] == new_value
                db[key] = old_value

        if forward:
            db[SchemaTurbo.current_state_lookup_key] = block_hash
        else:
            db[SchemaTurbo.current_state_lookup_key] = parent_hash
