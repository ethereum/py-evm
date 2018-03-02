from typing import Dict


class MemoryDB:
    kv_store: Dict[bytes, bytes] = None

    def __init__(self, kv_store: Dict[bytes, bytes]=None) -> None:
        if kv_store is None:
            self.kv_store = {}
        else:
            self.kv_store = kv_store

    def get(self, key: bytes) -> bytes:
        return self.kv_store[key]

    def set(self, key: bytes, value: bytes) -> None:
        self.kv_store[key] = value

    def exists(self, key: bytes) -> bool:
        return key in self.kv_store

    def delete(self, key: bytes) -> None:
        del self.kv_store[key]

    #
    # Dictionary API
    #
    def __getitem__(self, key: bytes) -> bytes:
        return self.get(key)

    def __setitem__(self, key: bytes, value: bytes) -> None:
        return self.set(key, value)

    def __delitem__(self, key: bytes) -> None:
        return self.delete(key)

    def __contains__(self, key: bytes) -> bool:
        return self.exists(key)
