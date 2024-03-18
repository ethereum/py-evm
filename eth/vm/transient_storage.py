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
    Address,
    JournalDBCheckpoint,
)
from eth.validation import (
    validate_canonical_address,
    validate_is_bytes,
    validate_uint256,
)

EMPTY_VALUE = b""  # note: stack.to_int(b"") == 0


class TransientStorage(TransientStorageAPI):
    def __init__(self) -> None:
        self._db = JournalDB(MemoryDB())

    @staticmethod
    def _get_key(address: Address, slot: int) -> bytes:
        return address + int_to_big_endian(slot)

    def get_transient_storage(self, address: Address, slot: int) -> bytes:
        validate_canonical_address(address)
        validate_uint256(slot)

        key = self._get_key(address, slot)
        return self._db.get(key, EMPTY_VALUE)

    def set_transient_storage(self, address: Address, slot: int, value: bytes) -> None:
        validate_canonical_address(address)
        validate_uint256(slot)
        validate_is_bytes(value)  # JournalDB requires `bytes` values

        key = self._get_key(address, slot)
        self._db[key] = value

    def record(self, checkpoint: JournalDBCheckpoint) -> None:
        self._db.record(checkpoint)

    def commit(self, checkpoint: JournalDBCheckpoint) -> None:
        self._db.commit(checkpoint)

    def discard(self, checkpoint: JournalDBCheckpoint) -> None:
        self._db.discard(checkpoint)

    def clear(self) -> None:
        self._db.clear()
