from eth_utils import (
    int_to_big_endian,
)

from eth.abc import (
    TransientStorageAPI,
)
from eth.db.backends.memory import (
    MemoryDB,
)
from eth.db.journal import (
    JournalDB,
)
from eth.typing import (
    Address, JournalDBCheckpoint,
)
from eth.validation import (
    validate_canonical_address,
    validate_uint256,
)


class TransientStorage(TransientStorageAPI):
    def __init__(self):
        self._transient_storage = JournalDB(MemoryDB())

    @staticmethod
    def _get_key(address: Address, slot: int) -> bytes:
        return address + int_to_big_endian(slot)

    def get_transient_storage(self, address: Address, slot: int) -> int:
        validate_canonical_address(address)
        validate_uint256(slot)

        key = self._get_key(address, slot)
        return self._transient_storage.get(key, 0)

    def set_transient_storage(self, address: Address, slot: int, value: bytes) -> None:
        validate_canonical_address(address)
        validate_uint256(slot)
        if not isinstance(value, bytes):
            raise TypeError("Value must be bytes")

        key = self._get_key(address, slot)
        self._transient_storage[key] = value

    def record(self, checkpoint: JournalDBCheckpoint) -> None:
        self._transient_storage.record(checkpoint)

    def commit(self, checkpoint: JournalDBCheckpoint) -> None:
        self._transient_storage.commit(checkpoint)

    def discard(self, checkpoint: JournalDBCheckpoint) -> None:
        self._transient_storage.discard(checkpoint)
